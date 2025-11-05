import os
from utils.pdf_utils import extract_acroform_fields
from utils.llm_utils import map_fields_to_cdm
from utils.data_utils import fetch_from_cdm
from utils.fill_utils import fill_acroform
from PyPDF2 import PdfReader

# ----------------------------
#  Canonical Data Model (CDM)
# ----------------------------
CDM = {
    "person.first_name": "Jane",
    "person.last_name": "Doe",
    "person.ssn": "123-45-6789",
    "person.address": "123 Main Street, New York, NY",
    "person.city": "New York",
    "person.state": "NY",
    "person.zip": "10001",
    "account.number": "SCHW12345",
    "account.type": "Individual",
    "bank.name": "Chase Bank"
}


# ----------------------------
#  Utility Functions
# ----------------------------

def detect_form_type(pdf_path):
    """Detect whether the PDF is an AcroForm or static."""
    reader = PdfReader(pdf_path)
    if "/AcroForm" in reader.trailer["/Root"]:
        return "acroform"
    return "static"


def process_form(pdf_path, output_path):
    """Main form processing pipeline."""
    print(f"📄 Processing form: {pdf_path}")

    form_type = detect_form_type(pdf_path)
    print(f"🔍 Detected form type: {form_type}")

    if form_type == "acroform":
        # 1. Extract fields
        fields = extract_acroform_fields(pdf_path)

        # 2. Identify empty fields
        empty_fields = [
            k for k, v in fields.items()
            if not v["value"] or str(v["value"]).strip() == ""
        ]
        print(f"🧾 Empty fields found: {empty_fields}")

        # 3. Normalize for LLM mapping
        normalized_fields = [fields[k]["clean_name"] for k in empty_fields]

        # 4. Run LLM mapping (batched + safe)
        llm_mapping = map_fields_to_cdm(normalized_fields, CDM)

        # 5. Re-associate normalized → real field names
        final_mapping = {}
        for raw, clean in zip(empty_fields, normalized_fields):
            if clean in llm_mapping and llm_mapping[clean]:
                final_mapping[raw] = llm_mapping[clean]

        # 6. Fetch values from CDM
        filled_data = fetch_from_cdm(final_mapping, CDM)

        # 7. Fill the AcroForm
        fill_acroform(pdf_path, filled_data, output_path)

        print(f"✅ Prefill complete → {output_path}")

    else:
        print("⚠️ Static form processing not implemented yet.")


# ----------------------------
#  Entry Point
# ----------------------------
if __name__ == "__main__":
    os.makedirs("filled_outputs", exist_ok=True)

    # Change to your test form
    form_path = "./sample_forms/complex_acro.pdf"
    output_path = "./filled_outputs/filled_output_acroform.pdf"

    process_form(form_path, output_path)
