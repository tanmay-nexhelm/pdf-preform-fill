import fitz  # PyMuPDF
import re

def extract_field_labels(pdf_path, search_radius=100):
    """
    Extract visual text labels for form fields in a PDF.

    Args:
        pdf_path: Path to the PDF file
        search_radius: Maximum distance (in pixels) to search for labels near fields

    Returns:
        Dict mapping field names to their visual labels
        Example: {"Last[0]": "Last Name:", "City[0]": "City"}
    """
    doc = fitz.open(pdf_path)
    field_labels = {}

    for page_num, page in enumerate(doc):
        # Extract all text blocks with their positions
        text_blocks = page.get_text("dict")["blocks"]

        # Get all form fields on this page
        widgets = page.widgets()

        for widget in widgets:
            field_name = widget.field_name
            field_rect = widget.rect  # (x0, y0, x1, y1)

            # Find text near this field
            label = find_nearby_text(field_rect, text_blocks, search_radius)

            if label:
                # Clean and normalize the label
                cleaned_label = clean_label_text(label)
                if cleaned_label:
                    field_labels[field_name] = cleaned_label

    doc.close()
    return field_labels


def find_nearby_text(field_rect, text_blocks, search_radius):
    """
    Find text blocks near a form field.

    Searches in priority order:
    1. Text directly above the field (most common for labels)
    2. Text to the left of the field
    3. Text below or right (less common)

    Args:
        field_rect: Rectangle of the form field (x0, y0, x1, y1)
        text_blocks: List of text blocks from page.get_text("dict")
        search_radius: Maximum distance to search

    Returns:
        Text string found near the field, or None
    """
    field_x0, field_y0, field_x1, field_y1 = field_rect
    field_center_x = (field_x0 + field_x1) / 2
    field_center_y = (field_y0 + field_y1) / 2

    candidates = []

    for block in text_blocks:
        # Skip non-text blocks (images, etc.)
        if block.get("type") != 0:
            continue

        # Extract text from block
        block_text = ""
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                block_text += span.get("text", "") + " "

        block_text = block_text.strip()
        if not block_text:
            continue

        # Get block position
        block_rect = block["bbox"]  # (x0, y0, x1, y1)
        block_x0, block_y0, block_x1, block_y1 = block_rect
        block_center_x = (block_x0 + block_x1) / 2
        block_center_y = (block_y0 + block_y1) / 2

        # Calculate distance from block to field
        distance_x = abs(block_center_x - field_center_x)
        distance_y = abs(block_center_y - field_center_y)
        distance = (distance_x ** 2 + distance_y ** 2) ** 0.5

        # Only consider blocks within search radius
        if distance > search_radius:
            continue

        # Determine position relative to field
        is_above = block_y1 < field_y0
        is_left = block_x1 < field_x0
        is_below = block_y0 > field_y1
        is_right = block_x0 > field_x1

        # Assign priority (lower is better)
        if is_above and abs(block_center_x - field_center_x) < 50:
            # Text directly above (most common pattern)
            priority = 1
        elif is_left and abs(block_center_y - field_center_y) < 20:
            # Text to the left, same vertical alignment
            priority = 2
        elif is_above:
            # Text above but not aligned
            priority = 3
        elif is_left:
            # Text to the left but not aligned
            priority = 4
        else:
            # Text below or to the right (uncommon for labels)
            priority = 5

        candidates.append({
            "text": block_text,
            "distance": distance,
            "priority": priority
        })

    if not candidates:
        return None

    # Sort by priority first, then by distance
    candidates.sort(key=lambda x: (x["priority"], x["distance"]))

    # Return the best candidate
    return candidates[0]["text"]


def clean_label_text(text):
    """
    Clean and normalize label text.

    Removes common artifacts like:
    - Trailing colons
    - Extra whitespace
    - Special characters that aren't part of the label
    - Asterisks (required field markers)

    Args:
        text: Raw text string

    Returns:
        Cleaned text string
    """
    if not text:
        return ""

    # Remove extra whitespace
    text = " ".join(text.split())

    # Remove trailing colons and asterisks
    text = text.rstrip(":*")

    # Remove leading/trailing whitespace again
    text = text.strip()

    # Remove text that looks like instructions rather than labels
    # (e.g., "Please enter", "Click here", etc.)
    if len(text) > 100:  # Labels are usually short
        return ""

    instruction_patterns = [
        r"^please\s",
        r"^click\s",
        r"^enter\s",
        r"^select\s",
        r"^check\s",
    ]

    for pattern in instruction_patterns:
        if re.match(pattern, text.lower()):
            return ""

    return text
