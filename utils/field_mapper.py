import json
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def map_fields_to_cdm_direct(actual_field_names, field_labels, cdm, chunk_size=40):
    """
    Map PDF fields to CDM keys using visual labels and semantic understanding.

    Args:
        actual_field_names: List of actual PDF field names
        field_labels: Dict mapping field names to their visual labels
        cdm: The Canonical Data Model dict

    Returns:
        Dict mapping actual field names to CDM keys
    """
    mapping = {}

    # Filter out noise fields
    ignore_patterns = [
        "FormMaster", "pageSet", "section", "subform", "border", "table",
        "btn", "QRCode", "signature", "SignLine", "CLRPNT", "Header",
        "Row", "Form", "Master", "subSection", "RB", "ck", "image",
        "#subform", "#pageSet", "BARCOD", "Checkbox", "DateSigned",
        "SignHere", "FullName"
    ]

    filtered_fields = [
        f for f in actual_field_names
        if not any(pattern in f for pattern in ignore_patterns)
        and len(f) > 2  # Skip very short field names
    ]

    if not filtered_fields:
        return mapping

    # Get list of available CDM keys
    cdm_keys = list(cdm.keys())

    # Process in chunks
    for i in range(0, len(filtered_fields), chunk_size):
        chunk = filtered_fields[i:i+chunk_size]

        # Create field info with labels
        field_info = {}
        for field_name in chunk:
            # Extract short field name for display
            short_name = field_name.split('.')[-1] if '.' in field_name else field_name
            label = field_labels.get(field_name, short_name)
            field_info[field_name] = {
                "label": label,
                "technical_name": short_name
            }

        prompt = f"""You are a PDF form field mapper. Map form fields to CDM keys using semantic understanding of field labels.

Form Fields with Visual Labels:
{json.dumps(field_info, indent=2)}

Available CDM Keys:
{json.dumps(cdm_keys, indent=2)}

Instructions:
- Use the "label" field to understand what data the field expects
- Match labels to CDM keys based on semantic meaning
- If no appropriate CDM key exists, use null

Semantic Guidelines:
- Labels about last names, surnames, family names → person.last_name
- Labels about first names, given names → person.first_name
- Labels about middle names, middle initial → person.middle_name
- Labels about cities, towns, municipalities → person.city
- Labels about states, provinces → person.state
- Labels about ZIP codes, postal codes → person.zip
- Labels about phone numbers, telephone → person.phone
- Labels about addresses, street addresses → person.address
- Labels about SSN, social security → person.ssn
- Labels about account numbers, account IDs → account.number
- Labels about bank names, financial institution → bank.name
- Labels about account types → account.type
- Labels about employer names, company names → plan.employer_name
- Labels about plan types, 401k, retirement plan → plan.type

Return ONLY valid JSON mapping field names to CDM keys:
{{
  "Last[0]": "person.last_name",
  "City[0]": "person.city",
  ...
}}
"""

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0,
                messages=[
                    {"role": "system", "content": "You are a precise field mapper that returns valid JSON. Map fields directly to CDM keys."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )

            chunk_mapping = json.loads(response.choices[0].message.content)
            mapping.update(chunk_mapping)
            print(f"Mapped chunk {i//chunk_size + 1} ({len(chunk)} fields)")

        except Exception as e:
            print(f"WARNING: Failed to map chunk {i//chunk_size + 1}: {e}")
            continue

    return mapping


def create_fill_mapping_direct(actual_field_names, field_labels, cdm):
    """
    Create fill mapping by mapping PDF fields to CDM keys using visual labels.

    Args:
        actual_field_names: List of actual PDF field names
        field_labels: Dict mapping field names to their visual labels
        cdm: The Canonical Data Model dict

    Returns:
        Dict mapping actual field names to values to fill
    """
    field_to_cdm = map_fields_to_cdm_direct(actual_field_names, field_labels, cdm)

    print("\nCreating field-to-value mapping...")
    fill_mapping = {}

    for actual_field, cdm_key in field_to_cdm.items():
        if cdm_key and cdm_key in cdm:
            value = cdm[cdm_key]
            if value and str(value).strip():  # Only fill non-empty values
                fill_mapping[actual_field] = value
            # Silently skip empty values
        # Silently skip unmapped fields to reduce noise

    return fill_mapping


