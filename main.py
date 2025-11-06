import os
from utils.fill_utils import fill_acroform
from utils.field_mapper import create_fill_mapping_direct
from utils.label_extractor import extract_field_labels
from PyPDF2 import PdfReader

# ----------------------------
#  Canonical Data Model (CDM)
# ----------------------------
CDM = {
    # Personal Information
    "person.first_name": "Jane",
    "person.middle_name": "Marie",
    "person.last_name": "Doe",
    "person.suffix": "Jr.",
    "person.ssn": "123-45-6789",
    "person.phone": "767-788-3272",
    "person.phone_extension": "123",
    "person.address": "123 Main Street, New York, NY",
    "person.city": "New York",
    "person.state": "NY",
    "person.zip": "10001",

    # Account Information
    "account.number": "SCHW12345",
    "account.type": "Individual",
    "bank.name": "Chase Bank",

    # Employer/Plan Information
    "plan.employer_name": "ABC Corporation",
    "plan.type": "401(k)",
    "plan.name": "ABC Corp 401(k) Plan",

    # Distribution Information
    "distribution.type": "One-Time",
    "distribution.onetime_cash_amount": "50000.00",
    "distribution.onetime_securities": "No",
    "distribution.recurring_cash_amount": "",
    "distribution.recurring_start_date": "",
    "distribution.recurring_frequency": "",
    "distribution.recurring_income_option": "",
    "distribution.recurring_income_start_date": "",
    "distribution.lump_sum": "Yes",

    # Tax Withholding
    "tax.federal_withholding_rate": "20",
    "tax.state_withholding": "NY",
    "tax.state_withholding_rate": "5"
}


# ----------------------------
#  Utility Functions
# ----------------------------

def detect_form_type(pdf_path):
    """Detect whether the PDF is an AcroForm or static."""
    reader = PdfReader(pdf_path)  # using PyPDF2 to read the PDF file
    if "/AcroForm" in reader.trailer["/Root"]:
        return "acroform"
    return "static"


def process_form(pdf_path, output_path):
    """
    Process PDF form by mapping fields to CDM and filling with data.

    Args:
        pdf_path: Path to input PDF form
        output_path: Path for output filled PDF
    """
    print(f"Processing form: {pdf_path}")

    # Get actual PDF field names
    reader = PdfReader(pdf_path)
    pdf_fields = reader.get_fields()
    if not pdf_fields:
        print("ERROR: No form fields found in PDF")
        return

    actual_field_names = list(pdf_fields.keys())
    print(f"Found {len(actual_field_names)} total fields in PDF")

    # Extract visual labels for form fields
    print("Extracting visual labels from PDF...")
    field_labels = extract_field_labels(pdf_path)
    print(f"Extracted labels for {len(field_labels)} fields")

    # Map fields to CDM keys using visual labels
    print("\n" + "="*80)
    print("Mapping PDF fields to CDM keys using visual labels...")
    print("="*80)
    filled_data = create_fill_mapping_direct(actual_field_names, field_labels, CDM)

    if not filled_data:
        print("WARNING: No fields were mapped successfully")
        return

    print(f"\nSuccessfully mapped {len(filled_data)} fields")

    # Fill form with mapped data
    fill_acroform(pdf_path, filled_data, output_path)

    print(f"Complete: {output_path}")

# ----------------------------
#  Entry Point
# ----------------------------
if __name__ == "__main__":
    os.makedirs("filled_outputs", exist_ok=True)

    # Change to your test form
    form_path = "./sample_forms/easy-acro.pdf"
    output_path = "./filled_outputs/filled_output_easy_acroform.pdf"

    process_form(form_path, output_path)
