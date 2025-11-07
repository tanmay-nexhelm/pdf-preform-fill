import os
from utils.fill_utils import fill_acroform
from utils.label_extractor import process_pdf_form
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


def process_form_simple(pdf_path, output_path, form_type_description):
    """
    Process PDF form with simplified workflow - single LLM call per page.

    Args:
        pdf_path: Path to input PDF form
        output_path: Path for output filled PDF
        form_type_description: Description of the form type and purpose
    """
    print(f"Processing form: {pdf_path}")
    print(f"Form Type: {form_type_description}\n")

    # Get actual PDF field names to verify form has fields
    reader = PdfReader(pdf_path)
    pdf_fields = reader.get_fields()
    if not pdf_fields:
        print("ERROR: No form fields found in PDF")
        return

    print(f"Found {len(pdf_fields)} total fields in PDF\n")

    # Process PDF with simplified workflow: extract fields + classify + map in one go
    print("="*80)
    print("PROCESSING PAGES WITH CHAIN-OF-THOUGHT REASONING")
    print("="*80 + "\n")

    field_to_cdm = process_pdf_form(pdf_path, CDM, form_type_description)

    if not field_to_cdm:
        print("\nWARNING: No fields were mapped successfully")
        return

    # Create fill mapping with CDM values
    filled_data = {}
    primary_count = 0
    for field_name, cdm_key in field_to_cdm.items():
        if cdm_key and cdm_key in CDM:
            value = CDM[cdm_key]
            if value and str(value).strip():  # Only fill non-empty values
                filled_data[field_name] = value
                primary_count += 1

    print(f"\n{'='*80}")
    print(f"RESULTS")
    print(f"{'='*80}")
    print(f"Mapped {len(field_to_cdm)} PRIMARY account holder fields")
    print(f"Filling {len(filled_data)} fields with data")
    secondary_skipped = len(pdf_fields) - len(field_to_cdm)
    print(f"Skipped {secondary_skipped} secondary entity fields (beneficiary, spouse, etc.)\n")

    # Fill form with mapped data
    fill_acroform(pdf_path, filled_data, output_path)

    print(f"Complete: {output_path}")

# ----------------------------
#  Entry Point
# ----------------------------
if __name__ == "__main__":
    os.makedirs("filled_outputs", exist_ok=True)

    # Change to your test form
    form_path = "./sample_forms/entity-account-form.pdf"
    output_path = "./filled_outputs/filled_output_entity-account-form.pdf"

    # Prompt user for form type
    print("="*80)
    print("PDF FORM AUTO-FILL SYSTEM")
    print("="*80)
    print(f"\nForm to process: {form_path}\n")
    print("Please describe the form type and purpose.")
    print("Examples:")
    print("  - 'IRA Distribution Form for requesting retirement account distributions'")
    print("  - '401(k) Rollover Form for transferring retirement funds'")
    print("  - 'Entity Account Application for opening business investment accounts'")
    print("  - 'Beneficiary Designation Form for naming account beneficiaries'\n")

    form_type = input("Enter form type description: ").strip()

    if not form_type:
        print("\nNo form type provided. Using default...")
        form_type = "Financial form for account holder information"

    print("\n" + "="*80 + "\n")

    process_form_simple(form_path, output_path, form_type)
