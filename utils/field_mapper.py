import json
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def map_fields_to_cdm_direct(actual_field_names, cdm, chunk_size=40):
    """
    Directly map PDF field names to CDM keys using LLM.

    Args:
        actual_field_names: List of actual PDF field names
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

        prompt = f"""You are a PDF form field mapper for financial documents.

Given these technical PDF field names and available CDM (Canonical Data Model) keys, map each field to the most appropriate CDM key.

PDF Field Names:
{json.dumps(chunk, indent=2)}

Available CDM Keys:
{json.dumps(cdm_keys, indent=2)}

Return a JSON mapping from PDF field name to CDM key. If no appropriate CDM key exists, use null.

Field Name Patterns:
- "Last[0]" or "LastName" → person.last_name
- "Middle[0]" → person.middle_name (if not available, use null)
- "AccountHoldersNam[0]" → person.first_name
- "First[0]" or "FirstName" → person.first_name
- "City[0]" or "CityField" → person.city
- "State[0]" or "StateField" → person.state
- "ZipCode[0]" or "Zip" → person.zip
- "DaytimePhoneNumber[0]" → person.phone
- "Extension[0]" → person.phone_extension
- "HomeLegalStreetAd[0]" or "StreetAddress" → person.address
- "SchwabAccountNumbe[0]" or "AccountNumber" → account.number
- "SSN[0]" or "SocialSecurityNumb[0]" → person.ssn
- "EmployerPlanNameo[0]" → plan.employer_name
- "BankName[0]" → bank.name
- "RoutingNumber[0]" → bank.routing (if not available, use null)
- "AccountType[0]" → account.type

Return ONLY valid JSON:
{{
  "Last[0]": "person.last_name",
  "City[0]": "person.city",
  "AccountHoldersNam[0]": "person.first_name",
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


def create_fill_mapping_direct(actual_field_names, cdm):
    """
    Create fill mapping by directly mapping PDF fields to CDM keys.

    Args:
        actual_field_names: List of actual PDF field names
        cdm: The Canonical Data Model dict

    Returns:
        Dict mapping actual field names to values to fill
    """
    field_to_cdm = map_fields_to_cdm_direct(actual_field_names, cdm)

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


