"""
Static PDF Processor with CDM Integration

This module integrates:
1. CDM Builder - Build canonical data model from database records
2. Textract Field Detection - Extract form fields from static PDFs
3. LLM Field Mapping - Classify PRIMARY/SECONDARY and map to CDM keys
4. Static PDF Filling - Fill PDFs using coordinate-based text overlay

Usage:
    from static_pdf_processor import process_static_pdf_with_cdm
    from cdm_builder import build_cdm_from_record

    # Build CDM
    record = {"first_name": "Jane", "last_name": "Doe", "ssn": "123-45-6789"}
    cdm = build_cdm_from_record(record)

    # Process PDF
    results = process_static_pdf_with_cdm(
        pdf_path="form.pdf",
        textract_json_path="form_textract.json",
        output_path="filled_form.pdf",
        form_type="IRA Distribution Form",
        cdm_data=cdm
    )
"""

import json
import sys
from typing import Dict, Any, List, Optional

# Import extracted utilities from static PDF processing
from utils.static_pdf_utils import (
    load_textract_json,
    find_empty_fields,
    fill_pdf_with_values
)

# Import existing LLM classification
from utils.label_extractor import classify_and_map_fields_llm


def extract_page_text_from_textract(textract_data: Dict[str, Any], page_number: int) -> str:
    """
    Extract full page text from Textract JSON LINE blocks.

    This replicates PyMuPDF's page.get_text("text") but extracts from Textract JSON,
    eliminating the need to reload the PDF with PyMuPDF for text extraction.

    Args:
        textract_data: Loaded Textract JSON response
        page_number: Page number (1-indexed, matching Textract)

    Returns:
        Full page text with line breaks, reading order preserved

    Example:
        >>> textract_data = load_textract_json("analyzeDocResponse.json")
        >>> page_text = extract_page_text_from_textract(textract_data, 1)
        >>> print(page_text[:100])
        charles
        SCHWAB
        Request a Required Minimum Distribution
        From Your Schwab IRA
        Page 1 of 8
    """
    blocks = textract_data.get('Blocks', [])
    lines = []

    # Extract LINE blocks for this page
    for block in blocks:
        if block.get('BlockType') == 'LINE' and block.get('Page') == page_number:
            bbox = block.get('Geometry', {}).get('BoundingBox', {})
            lines.append({
                'text': block.get('Text', ''),
                'top': bbox.get('Top', 0),
                'left': bbox.get('Left', 0)
            })

    # Sort by vertical position (top to bottom), then horizontal (left to right)
    lines.sort(key=lambda x: (x['top'], x['left']))

    # Join into full page text
    page_text = '\n'.join([line['text'] for line in lines])

    return page_text


def transform_textract_to_llm_format(textract_fields: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert Textract field format to LLM-compatible format.

    Transforms from Textract's key_text + bounding_box structure to the format
    expected by classify_and_map_fields_llm().

    Args:
        textract_fields: List of fields from find_empty_fields()
            Format: [{"key_text": "First Name", "page": 1, "bounding_box": {...}}, ...]

    Returns:
        List of LLM-compatible field descriptors
            Format: [{"field_id": "First Name", "full_field_id": "First Name", "x": 0.5, "y": 0.3}, ...]

    Example:
        >>> textract_fields = [
        ...     {"key_text": "Account Number", "page": 1,
        ...      "bounding_box": {"Left": 0.5, "Top": 0.3, "Width": 0.2, "Height": 0.05}}
        ... ]
        >>> llm_fields = transform_textract_to_llm_format(textract_fields)
        >>> print(llm_fields[0])
        {"field_id": "Account Number", "full_field_id": "Account Number", "x": 0.6, "y": 0.325}
    """
    llm_fields = []

    for field in textract_fields:
        bbox = field.get("bounding_box", {})

        # Calculate center point of bounding box
        # This gives a representative position for the field
        left = bbox.get("Left", 0.0)
        top = bbox.get("Top", 0.0)
        width = bbox.get("Width", 0.0)
        height = bbox.get("Height", 0.0)

        x = left + width / 2
        y = top + height / 2

        llm_fields.append({
            "field_id": field["key_text"],
            "full_field_id": field["key_text"],  # For Textract, these are the same
            "x": x,
            "y": y
        })

    return llm_fields


def classify_textract_fields_with_llm(
    textract_data: Dict[str, Any],
    cdm_schema: Dict[str, Any],
    form_type: str
) -> Dict[str, str]:
    """
    Classify Textract fields using LLM and map PRIMARY fields to CDM keys.

    This function orchestrates:
    1. Extract empty fields from Textract
    2. Extract page text for LLM context
    3. Transform fields to LLM format
    4. Call LLM to classify and map fields
    5. Return field_key_text → CDM_key mappings

    Args:
        textract_data: Loaded Textract JSON response
        cdm_schema: CDM data dictionary (used to show available keys to LLM)
        form_type: Description of form type (e.g., "IRA Distribution Form")

    Returns:
        Dictionary mapping field key_text to CDM keys
        Format: {"Account Holder Name First": "person.first_name", "SSN": "person.ssn", ...}
        Only includes PRIMARY fields that were successfully mapped.

    Example:
        >>> textract_data = load_textract_json("analyzeDocResponse.json")
        >>> cdm = {"person.first_name": "Jane", "person.ssn": "123-45-6789"}
        >>> mappings = classify_textract_fields_with_llm(
        ...     textract_data,
        ...     cdm,
        ...     "IRA Distribution Form"
        ... )
        >>> print(mappings)
        {"Account Holder Name First": "person.first_name", "Social Security Number": "person.ssn"}
    """
    # Get empty fields from Textract
    empty_fields = find_empty_fields(textract_data)

    # Get unique pages
    pages = sorted(set(field.get('page', 1) for field in empty_fields))

    all_mappings = {}

    print(f"🤖 Classifying {len(empty_fields)} fields across {len(pages)} pages with LLM...")

    for page_num in pages:
        # Extract page text from Textract (replaces PyMuPDF page.get_text())
        page_text = extract_page_text_from_textract(textract_data, page_num)

        # Get fields for this page
        page_fields = [f for f in empty_fields if f.get('page', 1) == page_num]

        # Transform to LLM format
        llm_fields = transform_textract_to_llm_format(page_fields)

        # Use existing LLM classification function
        # This is the same function used for AcroForm PDFs!
        mappings = classify_and_map_fields_llm(
            page_text,
            llm_fields,
            cdm_schema,
            form_type,
            page_num
        )

        all_mappings.update(mappings)

    print(f"✅ Classified fields. Mapped {len(all_mappings)} PRIMARY fields to CDM keys.")

    return all_mappings


def process_static_pdf_with_cdm(
    pdf_path: str,
    textract_json_path: str,
    output_path: str,
    form_type: str,
    cdm_data: Dict[str, Any],
    font_size: float = 8.0,
    baseline_offset: float = -2.0,
    debug_mode: bool = False
) -> Dict[str, Any]:
    """
    End-to-end static PDF processing with CDM integration.

    This is the main entry point that combines all components:
    1. Load Textract results (field detection + text)
    2. Use LLM to classify fields as PRIMARY/SECONDARY
    3. Map PRIMARY fields to CDM keys
    4. Fill PDF with CDM values at Textract coordinates

    Args:
        pdf_path: Path to blank form PDF
        textract_json_path: Path to Textract AnalyzeDocument JSON
        output_path: Where to save filled PDF
        form_type: Description for LLM (e.g., "IRA Distribution Form")
        cdm_data: Canonical data model dictionary
        font_size: Text font size in points (default: 8.0)
        baseline_offset: Vertical position adjustment (negative = above, default: -2.0)
        debug_mode: Enable visual debugging and detailed logging

    Returns:
        Statistics dictionary with:
        - total_fields: Total empty fields detected
        - mapped_fields: Fields mapped to CDM keys by LLM
        - filled_fields: Fields actually filled (have CDM data)
        - fill_rate: Percentage of mapped fields that were filled
        - skipped_secondary: Fields skipped as SECONDARY (beneficiaries, etc.)

    Example:
        >>> from cdm_builder import build_cdm_from_record
        >>>
        >>> # Build CDM from database
        >>> record = {
        ...     "first_name": "John",
        ...     "last_name": "DOE",
        ...     "ssn": "454545454",
        ...     "phone": "834578823"
        ... }
        >>> cdm = build_cdm_from_record(record)
        >>>
        >>> # Process PDF
        >>> results = process_static_pdf_with_cdm(
        ...     pdf_path="sch_min_dist-ira.pdf",
        ...     textract_json_path="analyzeDocResponse.json",
        ...     output_path="filled_output.pdf",
        ...     form_type="IRA Required Minimum Distribution Form",
        ...     cdm_data=cdm,
        ...     debug_mode=True
        ... )
        >>>
        >>> print(f"Filled {results['filled_fields']}/{results['total_fields']} fields")
        Filled 11/89 fields
    """
    print(f"\n📄 Processing: {pdf_path}")
    print(f"📋 Form Type: {form_type}")

    # Step 1: Load Textract results
    print(f"\n1️⃣  Loading Textract results...")
    textract_data = load_textract_json(textract_json_path)
    empty_fields = find_empty_fields(textract_data)
    print(f"   Found {len(empty_fields)} empty fields")

    # Step 2: Use LLM to classify and map fields to CDM
    print(f"\n2️⃣  Using LLM to classify and map fields...")
    field_to_cdm = classify_textract_fields_with_llm(
        textract_data,
        cdm_data,
        form_type
    )

    # Step 3: Create field_values dictionary by combining mappings with CDM data
    print(f"\n3️⃣  Mapping CDM data to fields...")
    field_values = {}
    for field in empty_fields:
        key_text = field["key_text"]
        cdm_key = field_to_cdm.get(key_text)

        if cdm_key and cdm_key in cdm_data:
            field_values[key_text] = cdm_data[cdm_key]
            if debug_mode:
                print(f"   ✓ {key_text} ← {cdm_key} = {cdm_data[cdm_key]}")

    print(f"   Prepared {len(field_values)} field values")

    # Step 4: Fill static PDF
    print(f"\n4️⃣  Filling PDF with values...")
    fill_pdf_with_values(
        pdf_path,
        output_path,
        empty_fields,
        field_values,
        font_size=font_size,
        baseline_offset=baseline_offset,
        debug_mode=debug_mode
    )

    # Step 5: Calculate and return statistics
    total_fields = len(empty_fields)
    mapped_fields = len(field_to_cdm)
    filled_fields = len(field_values)
    skipped_secondary = total_fields - mapped_fields
    fill_rate = (filled_fields / mapped_fields * 100) if mapped_fields > 0 else 0

    results = {
        "total_fields": total_fields,
        "mapped_fields": mapped_fields,
        "filled_fields": filled_fields,
        "skipped_secondary": skipped_secondary,
        "fill_rate": f"{fill_rate:.1f}%"
    }

    print(f"\n✅ Processing complete!")
    print(f"\n📊 Results:")
    print(f"   Total fields detected: {total_fields}")
    print(f"   Mapped to CDM (PRIMARY): {mapped_fields} ({mapped_fields/total_fields*100:.1f}%)")
    print(f"   Successfully filled: {filled_fields} ({fill_rate}% of mapped)")
    print(f"   Skipped (SECONDARY): {skipped_secondary}")
    print(f"\n💾 Saved to: {output_path}")

    return results


if __name__ == "__main__":
    # Example usage
    from cdm_builder import build_cdm_from_record

    # Build CDM from sample database record
    record = {
        "first_name": "John",
        "last_name": "DOE",
        "middle_name": "Q",
        "ssn": "454545454",
        "mobile": "834578823",
        "account_number": "123456789"
    }

    cdm = build_cdm_from_record(record)

    print("CDM Built:")
    for key, value in cdm.items():
        print(f"  {key}: {value}")

    # Process static PDF
    results = process_static_pdf_with_cdm(
        pdf_path="sch_min_dist-ira.pdf",
        textract_json_path="analyzeDocResponse.json",
        output_path="filled_output.pdf",
        form_type="IRA Required Minimum Distribution Form",
        cdm_data=cdm,
        debug_mode=True
    )
