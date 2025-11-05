from PyPDF2 import PdfReader

def extract_acroform_fields(pdf_path):
    """
    Extract all AcroForm fields (including nested ones),
    filter structural/XFA noise, and normalize names.
    """
    reader = PdfReader(pdf_path)
    fields = {}

    ignore_patterns = [
        "FormMaster", "pageSet", "section", "subform", "border", "table",
        "btn", "QRCode", "signature", "SignLine", "CLRPNT", "Header",
        "Row", "Form", "Master", "subSection", "ABA", "RB", "ck", "image"
    ]

    def _walk_fields(field_list):
        for f in field_list:
            field = f.get_object()
            name = field.get("/T")
            value = field.get("/V")

            if not name:
                continue
            if any(p.lower() in name.lower() for p in ignore_patterns):
                continue

            clean_name = (
                name.split("[")[0]
                .replace("_", "")
                .replace("\\", "")
                .strip()
            )
            fields[name] = {"value": value, "clean_name": clean_name}

            if "/Kids" in field:
                _walk_fields(field["/Kids"])

    if "/AcroForm" in reader.trailer["/Root"]:
        acroform = reader.trailer["/Root"]["/AcroForm"]
        if "/Fields" in acroform:
            _walk_fields(acroform["/Fields"])

    for page in reader.pages:
        if "/Annots" in page:
            _walk_fields(page["/Annots"])

    print(f"🧾 Total extracted fields: {len(fields)}")
    print("Sample field names:", list(fields.keys())[:10])
    return fields
