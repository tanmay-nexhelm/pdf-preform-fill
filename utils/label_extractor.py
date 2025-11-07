import fitz  # PyMuPDF
import json
from utils.llm_client import get_llm_client
import os

# Get LLM client (configured via environment variables)
llm_client = get_llm_client()

# Patterns to filter out irrelevant form fields
IGNORE_PATTERNS = [
    "FormMaster", "pageSet", "section", "subform", "border",
    "table", "btn", "button", "QRCode", "signature", "SignLine",
    "CLRPNT", "Header", "Footer", "Row", "Form", "Master",
    "subSection", "RB", "ck", "image", "#subform", "#pageSet",
    "BARCOD", "Checkbox", "DateSigned", "SignHere", "FullName",
    "Check", "check", "CHK", "chk", "Radio", "radio", "Option", "option"
]


def filter_noise_fields(fields):
    """
    Filter out irrelevant form fields based on widget ID patterns.

    Args:
        fields: List of field dicts with 'field_id', 'x', 'y'

    Returns:
        Filtered list of fields
    """
    filtered = []
    for field in fields:
        field_id = field.get("field_id", "")

        # Skip if matches ignore patterns
        if any(pattern in field_id for pattern in IGNORE_PATTERNS):
            continue

        # Skip very short field IDs
        if len(field_id) < 3:
            continue

        filtered.append(field)

    return filtered



def extract_page_fields(page):
    """
    Extract form field IDs with their X, Y positions from a page.

    Args:
        page: PyMuPDF page object

    Returns:
        List of dicts: [{"field_id": str, "x": float, "y": float}, ...]
    """
    fields = []
    widgets = page.widgets()

    for widget in widgets:
        field_name = widget.field_name
        field_rect = widget.rect  # (x0, y0, x1, y1)

        # Use center point of field for position
        x = (field_rect[0] + field_rect[2]) / 2
        y = (field_rect[1] + field_rect[3]) / 2

        # Extract short name (last part after dots)
        short_name = field_name.split('.')[-1] if '.' in field_name else field_name

        fields.append({
            "field_id": short_name,
            "full_field_id": field_name,
            "x": round(x, 1),
            "y": round(y, 1)
        })

    # Sort by Y position (top to bottom), then X position (left to right)
    fields.sort(key=lambda f: (f["y"], f["x"]))

    return fields


def classify_and_map_fields_llm(page_text, fields, cdm_schema, form_type, page_num, chunk_size=25):
    """
    Process fields in chunks using GPT-4o-mini for fast classification and mapping.

    Args:
        page_text: Full text content of the page
        fields: List of field dicts with field_id, x, y positions
        cdm_schema: Dict of CDM keys and their values
        form_type: Description of form type provided by user
        page_num: Page number (for context)
        chunk_size: Number of fields to process per LLM call (default: 25)

    Returns:
        Dict mapping field IDs to CDM keys: {"field_id": "cdm_key" or None}
    """
    if not fields:
        return {}

    # Process fields in chunks for faster response
    all_mappings = {}
    total_chunks = (len(fields) + chunk_size - 1) // chunk_size

    for chunk_idx in range(0, len(fields), chunk_size):
        chunk_fields = fields[chunk_idx:chunk_idx + chunk_size]
        chunk_num = chunk_idx // chunk_size + 1

        print(f"  Processing chunk {chunk_num}/{total_chunks} ({len(chunk_fields)} fields)...")

        chunk_mappings = _process_field_chunk(
            page_text, chunk_fields, cdm_schema, form_type, page_num
        )
        all_mappings.update(chunk_mappings)

    return all_mappings


def _process_field_chunk(page_text, fields, cdm_schema, form_type, page_num):
    """
    Process a chunk of fields with simplified chain-of-thought reasoning.

    Args:
        page_text: Full text content of the page
        fields: List of field dicts with field_id, x, y positions (chunk)
        cdm_schema: Dict of CDM keys and their values
        form_type: Description of form type provided by user
        page_num: Page number (for context)

    Returns:
        Dict mapping field IDs to CDM keys: {"field_id": "cdm_key" or None}
    """
    if not fields:
        return {}

    # Organize CDM keys by category
    cdm_categories = {
        "Personal Info": [k for k in cdm_schema.keys() if k.startswith("person.")],
        "Account Info": [k for k in cdm_schema.keys() if k.startswith("account.")],
        "Bank Info": [k for k in cdm_schema.keys() if k.startswith("bank.")]
    }

    cdm_text = "\n".join([
        f"{cat}: {', '.join(keys)}"
        for cat, keys in cdm_categories.items() if keys
    ])

    # Prepare fields for prompt (only include field_id, x, y)
    fields_for_prompt = [
        {"field_id": f["field_id"], "x": f["x"], "y": f["y"]}
        for f in fields
    ]

    prompt = f"""FORM TYPE: {form_type}

PAGE {page_num} TEXT:
{page_text}

FIELDS TO CLASSIFY (Y-ordered):
{json.dumps(fields_for_prompt, indent=2)}

CDM KEYS: {cdm_text}

TASK: For each field, determine:
1. PAGE ANALYSIS: Understand the purpose of the page section-wise:
   - PRIMARY = The person/entity submitting this form (YOUR account, YOUR information, the account holder)
   - SECONDARY = Third parties NOT submitting the form (beneficiaries, spouse, authorized users, receiving institutions, delivering firms)
   - **CRITICAL for transfer/rollover forms**: "YOUR [institution] account" is ALWAYS PRIMARY, even if it's the receiving/destination account in the transfer
     * Transfer direction (FROM institution A TO institution B) does NOT determine PRIMARY vs SECONDARY
     * Only check: Does the section header say "YOUR account", "your information", "account holder"? → PRIMARY
     * Example: "Tell Us About YOUR Schwab Account" = PRIMARY (even though Schwab is receiving the transfer)
   - Identify sections with multiple choice options (e.g., "Choose A, B, C, or D") → ALL fields in such sections are SECONDARY
   - Identify the boundaries of each section using headers and Y-positions

2. FIELD CLASSIFICATION: For each field, classify as PRIMARY or SECONDARY:
   - Is field in a choice-based section? → SECONDARY (requires user decision first)
   - Check page text for section context (which section is this field in?)
   - Check field ID for hints ("benef", "spouse", "auth", "trustee" = SECONDARY)
   - Check Y-position: fields grouped together usually belong to same entity
   - If uncertain → SECONDARY (safe default)

3. CDM MAPPING (PRIMARY fields only):
   - FullName/Name (combined) → person.full_name
   - FirstName/Given → person.first_name
   - LastName/Surname → person.last_name
   - SSN/TaxID → person.ssn
   - Phone/Tel → person.phone
   - Address (full) → person.address
   - Street (only) → person.street
   - City → person.city, State → person.state, ZIP → person.zip
   - AccountNum/AcctNum → account.number
   - AccountType → account.type
   - BankName → bank.name
   - If SECONDARY or no match → null

RULES:
- CRITICAL: Avoid all fields in sections with multiple choice options (e.g., "Choose A, B, C, or D", "Select one of the following")
  These sections require user selection before filling → mark ALL fields in such sections as SECONDARY
- **Transfer forms special rule**: Section headers with "YOUR account", "your information", "account holder" = PRIMARY (ignore transfer direction)
  * Don't overthink which account is source vs destination in transfer/rollover forms
  * Focus ONLY on possessive keywords indicating the form submitter's identity
- PRIMARY = Person/entity SUBMITTING the form (keywords: "your", "account holder", "applicant", "owner")
- SECONDARY = All other parties (keywords: "beneficiary", "spouse", "authorized user", "receiving firm", "delivering institution", "trustee")
- Don't fill checkbox/radio button fields themselves
- Don't make assumptions - base decisions strictly on page text and field ID
- Field IDs containing "benef"/"spouse"/"auth"/"trustee"/"deliver"/"receiv" → SECONDARY
- When uncertain → SECONDARY (safe default)

OUTPUT (valid JSON only):
{{
  "FirstName[0]": {{"cdm_key": "person.first_name", "reasoning": "Primary holder section, Y:150, FirstName → person.first_name"}},
  "benef_FirstName[0]": {{"cdm_key": null, "reasoning": "Beneficiary section, has 'benef' prefix → SECONDARY"}},
  "AcctNum[0]": {{"cdm_key": "account.number", "reasoning": "Primary section, AccountNum → account.number"}},
  "MailAddress[0]": {{"cdm_key": null, "reasoning": "Inside choice section 'Choose A, B, or C' → SECONDARY (requires user selection)"}}
}}

Return JSON for ALL {len(fields_for_prompt)} fields.
"""

    try:
        system_prompt = "You are a precise financial form analyzer. Return only valid JSON. Classify fields as PRIMARY or SECONDARY and map PRIMARY fields to CDM keys."

        result = llm_client.generate_json(
            system_prompt=system_prompt,
            user_prompt=prompt,
            temperature=0
        )

        # Display model reasoning for debugging
        print(f"\n  🧠 Model Reasoning:")
        for field_id, data in result.items():
            if isinstance(data, dict) and "reasoning" in data:
                cdm = data.get("cdm_key", "null")
                reasoning = data.get("reasoning", "")
                # Show mappings with reasoning
                if cdm:
                    print(f"    ✓ {field_id} → {cdm}")
                    print(f"      💭 {reasoning}")
                else:
                    print(f"    ✗ {field_id} → SECONDARY")
                    print(f"      💭 {reasoning}")
        print()  # blank line after reasoning section

        # Extract just the cdm_key mappings (remove reasoning from result)
        # Only include fields with valid (non-null, non-empty) CDM mappings
        mappings = {}
        for field_id, data in result.items():
            if isinstance(data, dict):
                cdm_key = data.get("cdm_key")
                # Only store if cdm_key is not None, not empty string, and not "null" string
                if cdm_key and cdm_key != "null":
                    mappings[field_id] = cdm_key
            else:
                # Handle case where LLM returns just a string value
                if data and data != "null":
                    mappings[field_id] = data

        return mappings

    except Exception as e:
        print(f"WARNING: LLM classification failed for page {page_num}: {e}")
        return {}


def process_pdf_form(pdf_path, cdm_schema, form_type):
    """
    Process entire PDF form with simplified workflow.

    Args:
        pdf_path: Path to PDF file
        cdm_schema: Dict of CDM keys and values
        form_type: Description of form type

    Returns:
        Dict mapping field IDs to CDM keys: {"field_id": "cdm_key"}
    """
    # Display LLM configuration
    print(f"Using LLM: {llm_client.get_info()}\n")

    doc = fitz.open(pdf_path)
    all_mappings = {}

    for page_num, page in enumerate(doc):
        # Extract page text
        page_text = page.get_text("text")

        # Extract fields with positions
        fields = extract_page_fields(page)

        # Filter out noise fields
        filtered_fields = filter_noise_fields(fields)

        if not filtered_fields:
            print(f"Page {page_num + 1}: No fields to process")
            continue

        print(f"Page {page_num + 1}: Processing {len(filtered_fields)} fields (filtered from {len(fields)} total)")

        # Single LLM call for classification + mapping
        mappings = classify_and_map_fields_llm(
            page_text,
            filtered_fields,
            cdm_schema,
            form_type,
            page_num + 1
        )

        # Store ONLY full field names to prevent collisions between sections
        # (e.g., PRIMARY "streetname[0]" vs SECONDARY "streetname[0]" in different sections)
        for field in filtered_fields:
            short_id = field["field_id"]
            full_id = field["full_field_id"]

            if short_id in mappings:
                cdm_key = mappings[short_id]
                # Double-check: only store non-null, non-empty CDM keys
                if cdm_key and isinstance(cdm_key, str) and cdm_key.strip():
                    # Only store full field name (not short name) to prevent collisions
                    all_mappings[full_id] = cdm_key

    doc.close()
    return all_mappings
