import os
import json
import re
from openai import OpenAI
import dotenv

dotenv.load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def safe_json_parse(text):
    """Try to safely parse or repair malformed JSON."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        repaired = re.sub(r'[\n\r]+', '', text).strip()
        if not repaired.endswith("}"):
            repaired += "}"
        try:
            return json.loads(repaired)
        except Exception:
            print("⚠️ Could not repair JSON, skipping mapping.")
            return {}

def chunk_list(lst, n):
    """Split list into chunks of n."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def call_llm_for_mapping(fields_chunk, cdm):
    """Call the LLM for one chunk of fields."""
    prompt = f"""
You are a precise data mapping assistant for a financial PDF form-filling tool.
Map each form field name to the most relevant key from the Canonical Data Model (CDM).

Rules:
- Only map client/account-related fields (ignore buttons, signatures, instructions).
- Match semantically similar names (e.g., "Acct #" → "account.number").
- Return valid JSON only, no text before/after.
- If unsure, return null.

Form field names:
{json.dumps(fields_chunk, indent=2)}

Canonical Data Model Keys:
{json.dumps(list(cdm.keys()), indent=2)}
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a data mapping assistant that returns only JSON."},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
        response_format={"type": "json_object"}
    )
    return safe_json_parse(response.choices[0].message.content)

def map_fields_to_cdm(empty_fields, cdm):
    """Batch fields, apply alias fallback, and call LLM with safe parsing."""
    print("🤖 Mapping form fields to CDM using LLM...")
    mapping = {}

    # Step 1 — Alias fallback
    aliases = {
        "NameAccountHolder": "person.first_name",
        "AccountHoldersNam": "person.last_name",
        "SocialSecurityNumb": "person.ssn",
        "Address": "person.address",
        "AccountNumber": "account.number",
        "City": "person.city",
        "State": "person.state",
        "ZipCode": "person.zip",
        "BankName": "bank.name",
        "BankaccountNumber": "account.number"
    }
    for field in empty_fields:
        for a, cdm_key in aliases.items():
            if a.lower() in field.lower():
                mapping[field] = cdm_key

    # Step 2 — Chunked LLM calls
    unmapped = [f for f in empty_fields if f not in mapping]
    for i, chunk in enumerate(chunk_list(unmapped, 40), 1):
        print(f"🤖 Mapping chunk {i} ({len(chunk)} fields)...")
        chunk_mapping = call_llm_for_mapping(chunk, cdm)
        mapping.update(chunk_mapping)

    # Step 3 — Cache mapping
    os.makedirs("mappings", exist_ok=True)
    with open("mappings/latest_mapping.json", "w") as f:
        json.dump(mapping, f, indent=2)

    print("✅ Mapping complete and cached → mappings/latest_mapping.json")
    return mapping
