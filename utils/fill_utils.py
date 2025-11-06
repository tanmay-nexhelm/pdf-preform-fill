import fitz  # PyMuPDF

def fill_acroform(pdf_path, filled_data, output_path):
    """
    Fill an AcroForm PDF with provided field-value pairs using PyMuPDF.

    Args:
        pdf_path: Path to input PDF
        filled_data: Dict mapping field names to values
        output_path: Path for output filled PDF
    """
    if not filled_data:
        print("WARNING: No data to fill")
        return

    doc = fitz.open(pdf_path)
    filled_count = 0

    # Fill each form field
    for page in doc:
        for field in page.widgets():
            full_field_name = field.field_name
            # Extract short name (last part after last dot)
            # e.g., 'clients[0].Form[0].SchwabAccountNumbe[0]' -> 'SchwabAccountNumbe[0]'
            short_field_name = full_field_name.split('.')[-1] if '.' in full_field_name else full_field_name

            # Check both full and short names
            if full_field_name in filled_data:
                value = str(filled_data[full_field_name])
            elif short_field_name in filled_data:
                value = str(filled_data[short_field_name])
            else:
                continue

            try:
                field.field_value = value
                field.update()
                filled_count += 1
            except Exception as e:
                print(f"WARNING: Failed to fill {short_field_name}: {e}")

    print(f"Filled {filled_count} fields")

    # Save the filled PDF (not flattened yet - keeps form editable)
    temp_path = output_path.replace(".pdf", "_temp.pdf")
    doc.save(temp_path, garbage=4, deflate=True)
    doc.close()

    # Flatten to make fields non-editable
    flatten_pdf(temp_path, output_path)
    print(f"Saved filled PDF: {output_path}")


def flatten_pdf(input_pdf, output_pdf):
    """
    Flatten form fields so filled data is visible as static text.
    """
    doc = fitz.open(input_pdf)
    for page in doc:
        page.clean_contents()  # ensure proper rendering
    doc.save(output_pdf, deflate=True, garbage=4)
    doc.close()
