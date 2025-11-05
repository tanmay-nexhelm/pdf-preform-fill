from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import NameObject, TextStringObject

def fill_acroform(pdf_path, data, output_path):
    """
    Fill AcroForm fields safely (handles nested + unlinked widgets).
    Converts string values to proper PDF TextStringObject.
    """
    reader = PdfReader(pdf_path)
    writer = PdfWriter()

    # Copy pages into writer
    for page in reader.pages:
        writer.add_page(page)

    # Fill top-level AcroForm fields (if they exist)
    writer.update_page_form_field_values(writer.pages[0], data)

    # Fallback: fill widget annotations manually
    for page in writer.pages:
        if "/Annots" in page:
            for field_ref in page["/Annots"]:
                widget = field_ref.get_object()
                field_name = widget.get("/T")
                if field_name and field_name in data:
                    value = data[field_name]
                    # Convert to proper PDF string object
                    widget.update({
                        NameObject("/V"): TextStringObject(str(value))
                    })

    # Ensure the AcroForm dictionary exists
    if "/AcroForm" in writer._root_object:
        writer._root_object["/AcroForm"].update({
            NameObject("/NeedAppearances"): NameObject("/true")
        })

    # Write output safely
    with open(output_path, "wb") as f:
        writer.write(f)

    print(f"✅ AcroForm filled successfully → {output_path}")


def fill_static_pdf(pdf_path, detected_fields, data, output_path):
    """Overlay text on coordinates for static PDFs."""
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)

    for f in detected_fields:
        label = f["label"]
        coords = f["coords"]
        if label in data:
            can.drawString(coords[0], coords[1], data[label])

    can.save()
    packet.seek(0)

    overlay = PdfReader(packet)
    base = PdfReader(pdf_path)
    writer = PdfWriter()

    for page in base.pages:
        overlay_page = overlay.pages[0]
        page.merge_page(overlay_page)
        writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)
    print(f"✅ Static PDF filled successfully → {output_path}")
