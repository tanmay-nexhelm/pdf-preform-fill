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


def classify_and_map_fields_llm(page_text, fields, cdm_schema, form_type, page_num, chunk_size=50):
    """
    Process fields in chunks using GPT-4o-mini for fast classification and mapping.

    Args:
        page_text: Full text content of the page
        fields: List of field dicts with field_id, x, y positions
        cdm_schema: Dict of CDM keys and their values
        form_type: Description of form type provided by user
        page_num: Page number (for context)
        chunk_size: Number of fields to process per LLM call (default: 50)

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


def _generate_dynamic_examples(cdm_schema):
    """
    Generate dynamic examples from actual CDM keys for the prompt.

    Args:
        cdm_schema: Dict of CDM keys and their values

    Returns:
        String with JSON examples adapted to the CDM schema
    """
    # Get sample CDM keys for examples
    sample_keys = list(cdm_schema.keys())[:3] if cdm_schema else []

    if not sample_keys:
        # Fallback generic examples
        return """{{
  "Field1[0]": {{"cdm_key": "cdm.key.example", "reasoning": "Primary submitter section, field matches CDM key purpose"}},
  "OtherPartyField[0]": {{"cdm_key": null, "reasoning": "Third party section → SECONDARY"}},
  "ChoiceField[0]": {{"cdm_key": null, "reasoning": "Inside choice section requiring user selection → SECONDARY"}}
}}"""

    # Generate examples using actual CDM keys
    example_primary = sample_keys[0]
    example_key_name = example_primary.split('.')[-1] if '.' in example_primary else example_primary

    examples = f"""{{
  "{example_key_name.title()}[0]": {{"cdm_key": "{example_primary}", "reasoning": "Primary submitter section at Y:150, field purpose matches '{example_primary}'"}},
  "ThirdParty_{example_key_name.title()}[0]": {{"cdm_key": null, "reasoning": "Third party section, not the form submitter → SECONDARY"}},
  "ChoiceOption[0]": {{"cdm_key": null, "reasoning": "Inside multi-choice section requiring user decision → SECONDARY"}}
}}"""

    return examples


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

    # Organize CDM keys by category for better presentation
    cdm_categories = {}
    for key in cdm_schema.keys():
        if '.' in key:
            category = key.split('.')[0].title()
            if category not in cdm_categories:
                cdm_categories[category] = []
            cdm_categories[category].append(key)
        else:
            if "Other" not in cdm_categories:
                cdm_categories["Other"] = []
            cdm_categories["Other"].append(key)

    cdm_text = "\n".join([
        f"{cat}: {', '.join(keys)}"
        for cat, keys in cdm_categories.items() if keys
    ])

    # Prepare fields for prompt (only include field_id, x, y)
    fields_for_prompt = [
        {"field_id": f["field_id"], "x": f["x"], "y": f["y"]}
        for f in fields
    ]

    # Generate dynamic examples from CDM schema
    dynamic_examples = _generate_dynamic_examples(cdm_schema)

    prompt = f"""FORM TYPE: {form_type}

PAGE {page_num} TEXT:
{page_text}

FIELDS TO CLASSIFY (Y-ordered):
{json.dumps(fields_for_prompt, indent=2)}

CDM KEYS: {cdm_text}

TASK: For each field, determine:

1. SECTION ANALYSIS - Identify who owns each section:
   Use these OWNERSHIP INDICATORS to classify sections:

   PRIMARY INDICATORS (form submitter/signer):
   - Possessive pronouns: "your", "my", "I", "me"
   - Identity terms: "applicant", "account holder", "owner", "primary", "participant"
   - Section headers like: "Your Information", "About You", "Account Holder Details"

   SECONDARY INDICATORS (other parties):
   - Other person references: "beneficiary", "spouse", "dependent", "joint owner", "authorized user"
   - Other institution references: "receiving firm", "delivering institution", "transfer agent"
   - Directional terms suggesting recipient: "to be sent to", "payable to", "recipient"

   CRITICAL PRINCIPLE: Focus on WHO the section describes, NOT the transaction flow
   - Section about "YOUR account" = PRIMARY (even if it's receiving/destination in a transfer)
   - Section about "Beneficiary" = SECONDARY (even if they're getting distributions)
   - Section about "Spouse" = SECONDARY (even if joint owner)

2. FIELD CLASSIFICATION LOGIC:

   Step 1: Determine section ownership using indicators above
   Step 2: Check for special cases:
   - Multi-choice sections ("Choose A, B, or C") → ALL fields SECONDARY (requires user decision)
   - Checkbox/radio fields themselves → SECONDARY (not data fields)

   Step 3: Classify field:
   - In PRIMARY section + not special case → PRIMARY
   - In SECONDARY section OR special case → SECONDARY
   - Uncertain → SECONDARY (safe default)

3. CDM MAPPING (PRIMARY fields only):
   - Match field semantic purpose to available CDM keys
   - Use field ID, section context, and position as hints
   - Refer to examples below for mapping patterns
   - If no clear CDM match → null

CORE PRINCIPLES:
1. Possessive language determines ownership ("your X" = PRIMARY)
2. Multi-choice sections always require user selection → SECONDARY
3. Focus on section headers and grouping, not individual field IDs
4. When in doubt about classification → SECONDARY
5. When in doubt about CDM mapping → null

OUTPUT (valid JSON only):
{dynamic_examples}

Return JSON for ALL {len(fields_for_prompt)} fields.
"""

    try:
        system_prompt = "You are a precise form analyzer. Return only valid JSON. Classify fields as PRIMARY (form submitter) or SECONDARY (other parties) and map PRIMARY fields to available CDM keys."

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
