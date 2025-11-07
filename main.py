"""
PDF Form Auto-Fill System using Claude Sonnet 4.5

This module provides functionality to automatically fill PDF forms using LLM-based
field classification and mapping to a Canonical Data Model (CDM).
"""

import os
from utils.fill_utils import fill_acroform
from utils.label_extractor import process_pdf_form
from PyPDF2 import PdfReader


def get_default_cdm():
    """
    Get default Canonical Data Model (CDM) with sample data.

    Returns:
        dict: CDM with personal and account information
    """
    return {
        # Personal Information
        "person.full_name": "Jane Marie Doe",
        "person.first_name": "Jane",
        "person.middle_name": "Marie",
        "person.last_name": "Doe",
        "person.suffix": "Jr.",
        "person.ssn": "123-45-6789",
        "person.phone": "767-788-3272",
        "person.phone_extension": "123",
        "person.address": "123 Main Street, New York, NY",
        "person.street": "123 Main Street",
        "person.city": "New York",
        "person.state": "NY",
        "person.zip": "10001",

        # Account Information
        "account.number": "SCHW12345",
        "account.type": "Individual",
        "bank.name": "Chase Bank"
    }


def process_pdf_form_with_cdm(pdf_path, output_path, form_type_description, cdm_data=None, verbose=True):
    """
    Process and fill a PDF form using LLM-based field classification.

    This function:
    1. Extracts form fields from the PDF
    2. Uses LLM to classify fields as PRIMARY (account holder) or SECONDARY (third parties)
    3. Maps PRIMARY fields to CDM keys
    4. Fills the form with CDM data
    5. Saves the filled PDF

    Args:
        pdf_path (str): Path to input PDF form
        output_path (str): Path for output filled PDF
        form_type_description (str): Description of the form type and purpose
                                     (e.g., "IRA Distribution Request Form")
        cdm_data (dict, optional): Canonical Data Model with user data.
                                   Uses default sample data if None.
        verbose (bool, optional): Print detailed progress. Defaults to True.

    Returns:
        dict: Results containing field counts and processing info, or None if error
    """
    cdm = cdm_data or get_default_cdm()

    if verbose:
        print(f"Processing form: {pdf_path}")
        print(f"Form Type: {form_type_description}\n")

    # Verify form has fields
    try:
        reader = PdfReader(pdf_path)
        pdf_fields = reader.get_fields()
    except Exception as e:
        if verbose:
            print(f"ERROR: Failed to read PDF: {e}")
        return None

    if not pdf_fields:
        if verbose:
            print("ERROR: No form fields found in PDF")
        return None

    if verbose:
        print(f"Found {len(pdf_fields)} total fields in PDF\n")
        print("="*80)
        print("PROCESSING WITH CLAUDE SONNET 4.5")
        print("="*80 + "\n")

    # Process PDF: classify fields and map to CDM
    try:
        field_to_cdm = process_pdf_form(pdf_path, cdm, form_type_description)
    except Exception as e:
        if verbose:
            print(f"ERROR: Failed to process form: {e}")
        return None

    if not field_to_cdm:
        if verbose:
            print("\nWARNING: No fields were mapped successfully")
        return None

    # Create fill mapping with CDM values
    filled_data = {}
    for field_name, cdm_key in field_to_cdm.items():
        if cdm_key and cdm_key in cdm:
            value = cdm[cdm_key]
            if value and str(value).strip():
                filled_data[field_name] = value

    # Print results
    if verbose:
        print(f"\n{'='*80}")
        print("RESULTS")
        print(f"{'='*80}")
        print(f"Mapped {len(field_to_cdm)} PRIMARY account holder fields")
        print(f"Filling {len(filled_data)} fields with data")
        secondary_skipped = len(pdf_fields) - len(field_to_cdm)
        print(f"Skipped {secondary_skipped} secondary entity fields (beneficiary, spouse, etc.)\n")

    # Fill and save form
    try:
        fill_acroform(pdf_path, filled_data, output_path)
        if verbose:
            print(f"Complete: {output_path}")
    except Exception as e:
        if verbose:
            print(f"ERROR: Failed to fill form: {e}")
        return None

    return {
        "total_fields": len(pdf_fields),
        "primary_mapped": len(field_to_cdm),
        "fields_filled": len(filled_data),
        "secondary_skipped": len(pdf_fields) - len(field_to_cdm),
        "output_path": output_path
    }


def main():
    """
    Interactive command-line interface for PDF form filling.
    """
    os.makedirs("filled_outputs", exist_ok=True)

    # Default form path (can be changed)
    form_path = "./sample_forms/entity-account-form.pdf"
    output_path = "./filled_outputs/filled_output.pdf"

    # Display interface
    print("="*80)
    print("PDF FORM AUTO-FILL SYSTEM")
    print("="*80)
    print(f"\nForm to process: {form_path}\n")
    print("Please describe the form type and purpose.")
    print("Examples:")
    print("  - 'IRA Distribution Form for requesting retirement account distributions'")
    print("  - '401(k) Rollover Form for transferring retirement funds'")
    print("  - 'Entity Account Application for opening business investment accounts'")
    print("  - 'Wire Transfer Request Form for sending funds'\n")

    form_type = input("Enter form type description: ").strip()

    if not form_type:
        print("\nNo form type provided. Using default...")
        form_type = "Financial form for account holder information"

    print("\n" + "="*80 + "\n")

    # Process form
    process_pdf_form_with_cdm(form_path, output_path, form_type)


if __name__ == "__main__":
    main()
