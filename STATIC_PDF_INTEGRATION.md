# Static PDF Integration with CDM & LLM Mapping

Complete guide for the integrated static PDF form filling system that combines CDM Builder, LLM field mapping, and coordinate-based PDF filling.

## Overview

This system automatically fills static PDF forms (forms without AcroForm fields) using:

1. **CDM Builder** (`cdm_builder.py`) - Converts database records to Canonical Data Model
2. **AWS Textract** - Detects form fields and extracts text via OCR
3. **LLM Field Mapper** (`utils/label_extractor.py`) - Classifies PRIMARY/SECONDARY fields and maps to CDM keys
4. **Static PDF Filler** (`utils/static_pdf_utils.py`) - Fills PDFs using coordinate-based text overlay

## Architecture

```
Database Record
    ↓
CDM Builder → CDM Data {"person.first_name": "Jane", ...}
    ↓
Textract JSON → Field Detection + Text Extraction
    ↓
LLM Mapper → Classification (PRIMARY/SECONDARY) + CDM Mapping
    ↓
Static PDF Filler → Text Overlay at Coordinates
    ↓
Filled PDF Output
```

## Installation

### Dependencies

```bash
pip install PyMuPDF anthropic openai python-dotenv
```

### Configuration

Create `.env` file:

```bash
# LLM Configuration
LLM_PROVIDER=anthropic  # or "openai"
LLM_MODEL=claude-sonnet-4-5-20250929
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-proj-...
```

## Usage

### Quick Start

```python
from static_pdf_processor import process_static_pdf_with_cdm
from cdm_builder import build_cdm_from_record

# 1. Build CDM from database
record = {
    "first_name": "John",
    "last_name": "DOE",
    "middle_name": "Q",
    "ssn": "454545454",
    "mobile": "834578823",
    "account_number": "SCH123312"
}

cdm = build_cdm_from_record(record)

# 2. Process PDF with intelligent mapping
results = process_static_pdf_with_cdm(
    pdf_path="form.pdf",
    textract_json_path="form_textract.json",
    output_path="filled_form.pdf",
    form_type="IRA Distribution Form",
    cdm_data=cdm,
    debug_mode=True
)

print(f"Filled {results['filled_fields']}/{results['total_fields']} fields")
```

### Step-by-Step

#### Step 1: Generate Textract JSON

You need to call AWS Textract's AnalyzeDocument API first:

```python
import boto3

textract = boto3.client('textract')

with open('form.pdf', 'rb') as document:
    response = textract.analyze_document(
        Document={'Bytes': document.read()},
        FeatureTypes=['FORMS']
    )

# Save response
import json
with open('form_textract.json', 'w') as f:
    json.dump(response, f)
```

#### Step 2: Build CDM

```python
from cdm_builder import build_cdm_from_record

# From database query
record = {
    "first_name": "Jane",
    "last_name": "Doe",
    "ssn": "123-45-6789",
    "phone": "555-1234",
    "email": "jane@example.com",
    "dob": "1980-01-15",
    "street": "123 Main St",
    "city": "Boston",
    "state": "MA",
    "zip": "02101",
    "account_number": "ACC123456",
    "bank_name": "First Bank",
    "routing_number": "123456789"
}

cdm = build_cdm_from_record(record)
```

**CDM Output:**
```python
{
    "person.first_name": "Jane",
    "person.last_name": "Doe",
    "person.ssn": "123-45-6789",
    "person.phone": "555-1234",
    "person.email": "jane@example.com",
    "person.dob": "1980-01-15",
    "person.street": "123 Main St",
    "person.city": "Boston",
    "person.state": "MA",
    "person.zip": "02101",
    "account.number": "ACC123456",
    "bank.name": "First Bank",
    "bank.routing": "123456789"
}
```

#### Step 3: Process PDF

```python
from static_pdf_processor import process_static_pdf_with_cdm

results = process_static_pdf_with_cdm(
    pdf_path="ira_form.pdf",
    textract_json_path="ira_form_textract.json",
    output_path="filled_ira_form.pdf",
    form_type="IRA Required Minimum Distribution Form",
    cdm_data=cdm,
    font_size=8.0,           # Adjust as needed
    baseline_offset=-2.0,    # Fine-tune vertical position
    debug_mode=True          # Enable detailed logging
)
```

## How It Works

### Text Extraction from Textract

Instead of loading the PDF again with PyMuPDF, we extract text directly from Textract JSON:

```python
def extract_page_text_from_textract(textract_data, page_number):
    """Extract full page text from LINE blocks"""
    blocks = textract_data['Blocks']
    lines = []

    for block in blocks:
        if block['BlockType'] == 'LINE' and block['Page'] == page_number:
            lines.append({
                'text': block['Text'],
                'top': block['Geometry']['BoundingBox']['Top']
            })

    lines.sort(key=lambda x: x['top'])
    return '\n'.join([line['text'] for line in lines])
```

### LLM Classification

The LLM analyzes page text and field positions to classify fields:

**PRIMARY Fields (Auto-filled):**
- Account holder information
- Identified by: "your", "my", "I", "applicant", "account holder"
- Examples: "Your Name", "Account Number", "Your Address"

**SECONDARY Fields (Skipped):**
- Third-party information
- Identified by: "beneficiary", "spouse", "joint owner", "receiving firm"
- Examples: "Beneficiary Name", "Spouse Information"

### CDM Mapping

For PRIMARY fields, the LLM maps to CDM keys based on semantic meaning:

```
Field: "Account Holder Name First" → CDM: "person.first_name"
Field: "Social Security Number" → CDM: "person.ssn"
Field: "Daytime Telephone" → CDM: "person.phone"
```

### PDF Filling

Text is overlaid at precise coordinates using baseline positioning:

```python
# Calculate baseline position
baseline_y = bottom_of_box + offset  # e.g., -2.0 pts above bottom

# Insert text at exact position
page.insert_text(
    Point(x, baseline_y),
    value,
    fontsize=8.0,
    color=(0, 0, 0)
)
```

## Configuration Options

### Font Size
```python
font_size=8.0   # Default
font_size=10.0  # Larger text
font_size=6.0   # Smaller text
```

### Baseline Offset
Controls vertical position of text:

```python
baseline_offset=-2.0   # 2pts above bottom (default)
baseline_offset=-3.0   # Higher up
baseline_offset=-1.0   # Closer to line
baseline_offset=0.0    # Exactly at bottom
```

### LLM Provider
Set in `.env`:

```bash
# Use Claude (recommended)
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-5-20250929

# Or use OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
```

## Debug Mode

Enable detailed logging and visual debugging:

```python
results = process_static_pdf_with_cdm(
    ...
    debug_mode=True
)
```

**Debug Output:**
- Field-by-field processing logs
- LLM classification reasoning
- CDM mapping decisions
- Visual rectangles and baselines in PDF
- Success/failure statistics

**Visual Markers:**
- 🔴 Red rectangle: Textract bounding box
- 🔵 Blue line: Text baseline position
- 🟢 Green dot: Text starting point

## Example Output

```
📄 Processing: sch_min_dist-ira.pdf
📋 Form Type: IRA Required Minimum Distribution Form

1️⃣  Loading Textract results...
   Found 89 empty fields

2️⃣  Using LLM to classify and map fields...
🤖 Classifying 89 fields across 8 pages with LLM...
✅ Classified fields. Mapped 25 PRIMARY fields to CDM keys.

3️⃣  Mapping CDM data to fields...
   Prepared 11 field values

4️⃣  Filling PDF with values...

📊 Fill Summary:
   Total fields found: 89
   ✅ Successfully filled: 11
   ⚠️  Skipped (no value): 78
   ❌ Failed: 0
   Fill rate: 11/89 (12.4%)

✅ Processing complete!

📊 Results:
   Total fields detected: 89
   Mapped to CDM (PRIMARY): 25 (28.1%)
   Successfully filled: 11 (44.0% of mapped)
   Skipped (SECONDARY): 64

💾 Saved to: filled_outputs/integrated_output.pdf
```

## Comparison: Manual vs Integrated

### Manual Approach (Old)
```python
# Had to manually create field_values dict
field_values = {
    "Schwab Individual Retirement Account (IRA) Number": "SCH123312",
    "Account Holder Name First": "John",
    "Daytime Telephone Number": "834578823",
    "Middle": "Q",
    "Last": "DOE",
    # ... manually type every field
}

fill_pdf_with_values(pdf, output, fields, field_values)
```

### Integrated Approach (New)
```python
# Just provide database record
record = {"first_name": "John", "last_name": "DOE", ...}
cdm = build_cdm_from_record(record)

# LLM automatically maps fields
process_static_pdf_with_cdm(pdf, textract, output, form_type, cdm)
```

**Benefits:**
- ✅ No manual field mapping required
- ✅ Automatically skips beneficiary/spouse fields
- ✅ Works across different form types
- ✅ Adapts to any database schema
- ✅ Intelligent field classification

## Troubleshooting

### Issue: Fields not filled

**Check:**
1. CDM has data for those keys
2. LLM mapped fields to CDM keys (check debug output)
3. Field names match exactly (case-sensitive)

**Solution:**
```python
# Enable debug mode to see mapping
process_static_pdf_with_cdm(..., debug_mode=True)
```

### Issue: Text appears in wrong position

**Adjust:**
```python
baseline_offset=-3.0  # Move text up
baseline_offset=-1.0  # Move text down
```

### Issue: Text too large/small

**Adjust:**
```python
font_size=7.0   # Smaller
font_size=9.0   # Larger
```

### Issue: LLM classifies field incorrectly

**Solution:**
Improve form_type description:
```python
# Bad:
form_type="Form"

# Good:
form_type="Individual IRA Required Minimum Distribution Request Form"
```

## Performance

- **Textract Processing**: ~5-10 seconds (AWS)
- **LLM Classification**: ~10-30 seconds (depends on pages/fields)
- **PDF Filling**: ~1-2 seconds
- **Total**: ~20-40 seconds per form

## Cost

- **Textract**: $1.50 per 1,000 pages
- **Claude Sonnet 4.5**: ~$0.01-0.05 per form
- **GPT-4o**: ~$0.02-0.08 per form

## Files Created

- `static_pdf_processor.py` - Main integration orchestrator
- `utils/static_pdf_utils.py` - PDF processing utilities
- `utils/label_extractor.py` - LLM classification (existing)
- `cdm_builder.py` - CDM generation (existing)
- `static-parse.ipynb` - Example notebook with demo

## Next Steps

1. **Test with your forms**: Try different PDF forms
2. **Tune parameters**: Adjust font_size and baseline_offset
3. **Add custom CDM patterns**: Extend `cdm_builder.py` for your field names
4. **Integrate with your database**: Replace sample records with real queries

## Support

For issues or questions:
- Check debug output first
- Review Textract JSON for field detection accuracy
- Test LLM classification with different models
- Adjust positioning parameters for your specific forms
