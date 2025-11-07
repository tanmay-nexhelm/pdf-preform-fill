#!/usr/bin/env python3
"""
Test Claude Sonnet 4.5 on all forms and store results in claude folder.
"""

import os
import time
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

# Test configurations
TEST_FORMS = [
    {
        "name": "entity-account-form",
        "path": "./sample_forms/entity-account-form.pdf",
        "form_type": "Entity Account Application for opening business investment accounts"
    },
    {
        "name": "easy-acro",
        "path": "./sample_forms/easy-acro.pdf",
        "form_type": "Simple account application form for individual investors"
    },
    {
        "name": "complex-acro",
        "path": "./sample_forms/complex_acro.pdf",
        "form_type": "IRA Distribution Request Form for requesting retirement account distributions"
    }
]


def test_form(form_config):
    """Test a single form with Claude Sonnet."""

    form_name = form_config["name"]
    form_path = form_config["path"]
    form_type = form_config["form_type"]
    output_path = f"./filled_outputs/claude/claude_sonnet_{form_name}.pdf"

    print("="*80)
    print(f"TESTING: {form_name}")
    print("="*80)
    print(f"Form: {form_path}")
    print(f"Form Type: {form_type}\n")

    # Get field count
    reader = PdfReader(form_path)
    pdf_fields = reader.get_fields()
    if not pdf_fields:
        print("ERROR: No form fields found in PDF")
        return None

    print(f"Found {len(pdf_fields)} total fields in PDF\n")

    # Process with Claude Sonnet
    print("="*80)
    print("PROCESSING WITH CLAUDE SONNET 4.5")
    print("="*80 + "\n")

    start_time = time.time()

    field_to_cdm = process_pdf_form(form_path, CDM, form_type)

    elapsed_time = time.time() - start_time

    if not field_to_cdm:
        print("\nWARNING: No fields were mapped successfully")
        return None

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
    print(f"Complete: {output_path}\n")

    return {
        "form_name": form_name,
        "total_fields": len(pdf_fields),
        "primary_mapped": len(field_to_cdm),
        "fields_filled": len(filled_data),
        "secondary_skipped": secondary_skipped,
        "processing_time": elapsed_time,
        "output_path": output_path
    }


def main():
    """Test all forms with Claude Sonnet."""

    os.makedirs("filled_outputs/claude", exist_ok=True)

    print("\n" + "="*80)
    print("CLAUDE SONNET 4.5 TESTING SUITE")
    print("="*80 + "\n")

    results = []

    for form_config in TEST_FORMS:
        result = test_form(form_config)
        if result:
            results.append(result)
        print("\n")

    # Summary
    print("="*80)
    print("SUMMARY: CLAUDE SONNET 4.5 RESULTS")
    print("="*80)
    print(f"\n{'Form':<25} {'Time':<10} {'Total':<10} {'Primary':<10} {'Filled':<10} {'Skipped':<10}")
    print("-"*80)

    for result in results:
        print(f"{result['form_name']:<25} "
              f"{result['processing_time']:<10.1f} "
              f"{result['total_fields']:<10} "
              f"{result['primary_mapped']:<10} "
              f"{result['fields_filled']:<10} "
              f"{result['secondary_skipped']:<10}")

    print("\n" + "="*80)
    print(f"Total processing time: {sum(r['processing_time'] for r in results):.1f} seconds")
    print(f"All filled PDFs saved to: ./filled_outputs/claude/")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
