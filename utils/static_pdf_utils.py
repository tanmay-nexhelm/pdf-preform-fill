"""
Static PDF Utilities

Helper functions for processing static PDFs with Textract.
These functions are extracted from static-parse.ipynb for reusability.
"""

import json
from typing import Dict, Any, List, Optional
import fitz


def load_textract_json(path: str) -> Dict[str, Any]:
    """Load AWS Textract AnalyzeDocument response JSON."""
    with open(path, "r") as f:
        return json.load(f)


def build_block_map(blocks: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Map block Id -> block object for quick lookup."""
    return {b["Id"]: b for b in blocks if "Id" in b}


def get_relationship_ids(block: Dict[str, Any], rel_type: str) -> List[str]:
    """Get list of related block Ids of a given relationship type (e.g. CHILD, VALUE)."""
    ids: List[str] = []
    for rel in block.get("Relationships", []):
        if rel.get("Type") == rel_type:
            ids.extend(rel.get("Ids", []))
    return ids


def get_text_from_block(block: Dict[str, Any], block_map: Dict[str, Dict[str, Any]]) -> str:
    """
    Return concatenated text for a KEY or VALUE block by joining the text of its CHILD WORD blocks.
    """
    child_ids = get_relationship_ids(block, "CHILD")
    words: List[str] = []
    for cid in child_ids:
        child = block_map.get(cid)
        if not child:
            continue
        if child.get("BlockType") == "WORD":
            words.append(child.get("Text", ""))
    return " ".join(words).strip()


def is_checkbox_field(value_block: Optional[Dict[str, Any]],
                      block_map: Dict[str, Dict[str, Any]]) -> bool:
    """
    Return True if this VALUE block represents a checkbox / radio-style field.

    We define that as: the VALUE block has at least one SELECTION_ELEMENT child.
    """
    if value_block is None:
        return False

    child_ids = get_relationship_ids(value_block, "CHILD")
    if not child_ids:
        return False

    for cid in child_ids:
        child = block_map.get(cid)
        if not child:
            continue
        if child.get("BlockType") == "SELECTION_ELEMENT":
            return True

    return False


def is_value_block_empty(value_block: Optional[Dict[str, Any]],
                         block_map: Dict[str, Dict[str, Any]]) -> bool:
    """
    Decide if a VALUE block is "empty" (for non-checkbox fields).

    Rules:
      - If there is no VALUE block at all -> empty.
      - If VALUE has no children -> empty.
      - Ignore SELECTION_ELEMENTs here (checkbox logic is handled separately).
      - Look at WORD children:
          * Join all words into a string.
          * Strip spaces, underscores, and dashes.
          * If nothing is left -> empty (only lines / underscores).
          * Else -> NOT empty.
    """
    if value_block is None:
        return True

    child_ids = get_relationship_ids(value_block, "CHILD")
    if not child_ids:
        return True

    words: List[str] = []

    for cid in child_ids:
        child = block_map.get(cid)
        if not child:
            continue
        if child.get("BlockType") == "WORD":
            words.append(child.get("Text", ""))

    if not words:
        return True

    # Clean the text to ignore printed lines like "_____"
    joined = " ".join(words)
    cleaned = joined.replace(" ", "").replace("_", "").replace("-", "").strip()

    return cleaned == ""


def find_empty_fields(textract_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    From a Textract AnalyzeDocument JSON, return a list of empty fields with:
      - key_text
      - page
      - bounding_box (Left, Top, Width, Height)

    NOTE: Checkbox / radio fields (VALUE blocks that have SELECTION_ELEMENT children)
          are completely skipped and NOT returned, even if "empty".
    """
    blocks = textract_data.get("Blocks", [])
    block_map = build_block_map(blocks)

    empty_fields: List[Dict[str, Any]] = []

    for block in blocks:
        # Only look at KEY blocks (form labels)
        if block.get("BlockType") != "KEY_VALUE_SET":
            continue
        if "KEY" not in block.get("EntityTypes", []):
            continue

        key_block = block
        key_text = get_text_from_block(key_block, block_map)

        # Find corresponding VALUE block
        value_ids = get_relationship_ids(key_block, "VALUE")
        value_block = block_map.get(value_ids[0]) if value_ids else None

        # Skip checkbox / radio fields entirely
        if is_checkbox_field(value_block, block_map):
            continue

        # Decide if that value area is empty
        if not is_value_block_empty(value_block, block_map):
            continue  # this field is filled, skip it

        # Coordinates: use the VALUE block's bounding box if available,
        # otherwise fall back to KEY block's bounding box
        source_block = value_block if value_block is not None else key_block
        bbox = source_block.get("Geometry", {}).get("BoundingBox", {})
        page = source_block.get("Page")

        empty_fields.append({
            "key_text": key_text,
            "page": page,
            "bounding_box": {
                "Left": bbox.get("Left"),
                "Top": bbox.get("Top"),
                "Width": bbox.get("Width"),
                "Height": bbox.get("Height"),
            }
        })

    return empty_fields


def fill_pdf_with_values(
    template_pdf_path: str,
    output_pdf_path: str,
    empty_fields: List[Dict[str, Any]],
    field_values: Dict[str, str],
    font_size: float = 7.0,
    debug_mode: bool = False,
    baseline_offset: float = -2.0,
):
    """
    Superimpose text values onto a static PDF using Textract field coordinates.

    Uses insert_text() with baseline positioning instead of insert_textbox() to avoid
    overflow issues with small bounding boxes.

    - template_pdf_path: path to the blank form PDF
    - output_pdf_path: where to save the filled PDF
    - empty_fields: list from find_empty_fields() (key_text, page, bounding_box)
    - field_values: mapping from key_text -> value to write
    - baseline_offset: Points above (-) or below (+) the bottom of bounding box to place text baseline
    - debug_mode: if True, draws rectangles and shows detailed logs
    """
    doc = fitz.open(template_pdf_path)

    filled_count = 0
    skipped_count = 0
    failed_count = 0

    for field in empty_fields:
        key = field["key_text"]
        if key not in field_values:
            skipped_count += 1
            if debug_mode:
                print(f"⚠️  SKIPPED: '{key}' - no value in field_values dict")
            continue

        value = field_values[key]
        if not value or str(value).strip() == "":
            skipped_count += 1
            if debug_mode:
                print(f"⚠️  SKIPPED: '{key}' - empty value provided")
            continue

        page_index = (field["page"] or 1) - 1
        if page_index >= len(doc):
            failed_count += 1
            if debug_mode:
                print(f"❌ FAILED: '{key}' - invalid page {page_index + 1}")
            continue

        page = doc[page_index]

        bbox = field["bounding_box"]
        left = bbox.get("Left", 0.0)
        top = bbox.get("Top", 0.0)
        width = bbox.get("Width", 0.0)
        height = bbox.get("Height", 0.0)

        # Convert normalized coords to PDF coordinates
        page_width = page.rect.width
        page_height = page.rect.height

        x0 = left * page_width
        y0 = top * page_height
        x1 = (left + width) * page_width
        y1 = (top + height) * page_height

        original_rect = fitz.Rect(x0, y0, x1, y1)

        if original_rect.width <= 0 or original_rect.height <= 0:
            failed_count += 1
            if debug_mode:
                print(f"❌ FAILED: '{key}' - invalid rect dimensions")
            continue

        # Calculate text baseline position
        # Place text baseline slightly above the bottom of the bounding box
        baseline_y = y1 + baseline_offset
        text_position = fitz.Point(x0, baseline_y)

        # Debug mode: console logging only (visual boxes removed)
        if debug_mode:
            print(f"🔍 DEBUG: '{key}' -> '{value}'")
            print(f"   Page: {page_index + 1}")
            print(f"   Bounding box: {original_rect} (height: {original_rect.height:.2f}pts)")
            print(f"   Baseline Y: {baseline_y:.2f} (offset: {baseline_offset}pts from bottom)")
            print(f"   Text position: {text_position}")
            print(f"   Font size: {font_size:.2f}pts")

        # Insert text at baseline position
        try:
            # Using insert_text() instead of insert_textbox()
            # This places text at exact coordinates without worrying about box constraints
            rc = page.insert_text(
                text_position,
                str(value),
                fontsize=font_size,
                fontname="helv",
                color=(0, 0, 0),
                overlay=True,
            )

            filled_count += 1
            if debug_mode:
                print(f"✅ SUCCESS: '{key}' filled at baseline")

        except Exception as e:
            failed_count += 1
            if debug_mode:
                print(f"❌ EXCEPTION: '{key}' - {str(e)}")

    # Save filled PDF
    doc.save(output_pdf_path)
    doc.close()

    # Print summary
    total = len(empty_fields)
    print(f"\n📊 Fill Summary:")
    print(f"   Total fields found: {total}")
    print(f"   ✅ Successfully filled: {filled_count}")
    print(f"   ⚠️  Skipped (no value): {skipped_count}")
    print(f"   ❌ Failed: {failed_count}")
    print(f"   Fill rate: {filled_count}/{total} ({100*filled_count/total if total > 0 else 0:.1f}%)")
