#!/usr/bin/env python3
"""Test script for complex_acro.pdf - IRA Distribution form."""

import os
from utils.fill_utils import fill_acroform
from utils.label_extractor import process_pdf_form
from PyPDF2 import PdfReader

# Canonical Data Model (CDM)
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

def test_complex_form():
    """Test the optimized system on complex_acro.pdf - IRA Distribution."""

    # Setup
    form_path = "./sample_forms/complex_acro.pdf"
    output_path = "./filled_outputs/filled_output_complex_acro.pdf"
    form_type = "IRA Distribution Request Form for requesting retirement account distributions"

    os.makedirs("filled_outputs", exist_ok=True)

    print("="*80)
    print("TESTING OPTIMIZED SYSTEM ON COMPLEX_ACRO.PDF")
    print("="*80)
    print(f"\nForm: {form_path}")
    print(f"Form Type: {form_type}\n")

    # Get field count
    reader = PdfReader(form_path)
    pdf_fields = reader.get_fields()
    if not pdf_fields:
        print("ERROR: No form fields found in PDF")
        return

    print(f"Found {len(pdf_fields)} total fields in PDF\n")

    # Process with simplified workflow
    print("="*80)
    print("PROCESSING WITH OPTIMIZED CHAIN-OF-THOUGHT REASONING")
    print("="*80 + "\n")

    import time
    start_time = time.time()

    field_to_cdm = process_pdf_form(form_path, CDM, form_type)

    elapsed_time = time.time() - start_time

    if not field_to_cdm:
        print("\nWARNING: No fields were mapped successfully")
        return

    # Create fill mapping
    filled_data = {}
    for field_name, cdm_key in field_to_cdm.items():
        if cdm_key and cdm_key in CDM:
            value = CDM[cdm_key]
            if value and str(value).strip():
                filled_data[field_name] = value

    # Print results
    print(f"\n{'='*80}")
    print(f"RESULTS")
    print(f"{'='*80}")
    print(f"Processing time: {elapsed_time:.1f} seconds")
    print(f"Mapped {len(field_to_cdm)} PRIMARY account holder fields")
    print(f"Filling {len(filled_data)} fields with data")
    secondary_skipped = len(pdf_fields) - len(field_to_cdm)
    print(f"Skipped {secondary_skipped} secondary entity fields (beneficiary, spouse, etc.)\n")

    # Fill form
    fill_acroform(form_path, filled_data, output_path)
    print(f"Complete: {output_path}")

if __name__ == "__main__":
    test_complex_form()
