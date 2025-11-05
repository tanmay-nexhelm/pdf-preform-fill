import pytesseract
from pdf2image import convert_from_path
from PIL import Image

def extract_text_from_static(pdf_path):
    """
    Extracts text and layout info from static PDFs using Tesseract OCR.
    Returns list of dicts with label + dummy coordinates.
    """
    images = convert_from_path(pdf_path)
    all_fields = []

    for i, image in enumerate(images):
        text = pytesseract.image_to_string(image)
        print(f"📄 OCR Text Page {i+1}:\n{text[:200]}...")

        # Simple heuristic to find fields (e.g., lines with ':')
        for line in text.splitlines():
            if ":" in line:
                label = line.split(":")[0].strip()
                all_fields.append({
                    "page": i,
                    "label": label,
                    "coords": [100, 500 - 20 * len(all_fields)]  # dummy coords for demo
                })
    return all_fields
