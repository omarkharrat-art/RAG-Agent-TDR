import sys
import pytesseract
from pytesseract import Output
import fitz
import json
import os
from PIL import Image

# Fix Unicode output on Windows terminals (cp1252 -> utf-8)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# ============================================
# SET TESSERACT PATH FIRST (BEFORE USE)
# ============================================
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# The system Tesseract only ships the English model. Our TDRs are mostly
# French, so we bundle fra.traineddata under backend/ingestion/tessdata/ and
# point Tesseract at it via TESSDATA_PREFIX. If the French pack is missing we
# fall back to English, which still works (just less accurate on accents).
_LOCAL_TESSDATA = os.path.join(os.path.dirname(__file__), "tessdata")
if os.path.exists(os.path.join(_LOCAL_TESSDATA, "fra.traineddata")):
    os.environ["TESSDATA_PREFIX"] = _LOCAL_TESSDATA
    OCR_LANG = "fra+eng"
else:
    OCR_LANG = "eng"

# ============================================
# CONFIGURATION
# ============================================
INPUT_FOLDER = "backend/data/raw"
OUTPUT_FILE = "backend/data/extracted/phase1_extracted.json"
OCR_DPI = 300
MIN_CHARS_THRESHOLD = 200
# Horizontal gap (in pixels at OCR_DPI) above which two words are treated as
# being in different table columns, separated by ' | ' in the output.
COLUMN_GAP_PX = 40

os.makedirs("backend/data/extracted", exist_ok=True)

# ============================================
# OCR EXTRACTION FUNCTION
# ============================================
def _reconstruct_layout(img) -> str:
    """OCR a page image while preserving row/column structure.

    Plain image_to_string() flattens tables into a word stream, losing which
    value belongs to which cell. Instead we use image_to_data() to get each
    word's position, then:
      - group words into lines using Tesseract's block/paragraph/line ids;
      - within a line, insert ' | ' where there is a large horizontal gap
        between consecutive words (a column boundary).
    The result keeps table rows on one line with '|'-separated columns, so the
    downstream LLM can tell, e.g., which score pairs with which criterion.
    """
    data = pytesseract.image_to_data(img, lang=OCR_LANG, output_type=Output.DICT)
    n = len(data["text"])

    # Bucket words by their (block, paragraph, line) key so each dict entry is
    # one visual line of text.
    lines: dict[tuple, list[dict]] = {}
    for i in range(n):
        word = data["text"][i].strip()
        if not word:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append(
            {"text": word, "left": data["left"][i], "width": data["width"][i]}
        )

    out_lines = []
    for key in sorted(lines.keys()):
        words = sorted(lines[key], key=lambda w: w["left"])
        parts = []
        prev_right = None
        for w in words:
            if prev_right is not None:
                gap = w["left"] - prev_right
                parts.append(" | " if gap > COLUMN_GAP_PX else " ")
            parts.append(w["text"])
            prev_right = w["left"] + w["width"]
        out_lines.append("".join(parts))
    return "\n".join(out_lines)


def extract_with_ocr(filepath):
    """Extract text from PDF using OCR, preserving table layout."""
    try:
        doc = fitz.open(filepath)
        full_text = ""

        for page_num, page in enumerate(doc, 1):
            try:
                pix = page.get_pixmap(matrix=fitz.Matrix(OCR_DPI/72, OCR_DPI/72))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                ocr_text = _reconstruct_layout(img)
                full_text += f"\n--- Page {page_num} ---\n{ocr_text}"
            except Exception as page_error:
                print(f"         Page {page_num} error: {page_error}")
                continue

        doc.close()
        return full_text.strip() if full_text else None

    except Exception as e:
        print(f"       ❌ OCR Error: {e}")
        return None

# ============================================
# GET ALL PDFS
# ============================================
pdf_files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith('.pdf')]

print("=" * 50)
print("📄 PHASE 1: TEXT EXTRACTION + OCR FALLBACK")
print("=" * 50)
print(f"\n📁 Input folder: {INPUT_FOLDER}")
print(f"📁 Found {len(pdf_files)} TDR PDF files")
print(f"📍 Tesseract path: C:\\Program Files\\Tesseract-OCR\\tesseract.exe\n")

results = []
standard_count = 0
ocr_count = 0
failed_count = 0

for filename in pdf_files:
    filepath = os.path.join(INPUT_FOLDER, filename)
    print(f"📖 Reading: {filename}")
    
    try:
        doc = fitz.open(filepath)
        full_text = ""
        
        for page in doc:
            full_text += page.get_text()
        
        doc.close()
        char_count = len(full_text.strip())
        
        if char_count >= MIN_CHARS_THRESHOLD:
            print(f"   └─ ✅ {char_count} characters extracted\n")
            results.append({
                "filename": filename,
                "content": full_text.strip(),
                "extraction_method": "standard"
            })
            standard_count += 1
        else:
            print(f"   └─ ⚠️  Only {char_count} chars, using OCR...")
            ocr_text = extract_with_ocr(filepath)
            
            if ocr_text and len(ocr_text) > 0:
                print(f"       ✅ OCR extracted {len(ocr_text)} characters\n")
                results.append({
                    "filename": filename,
                    "content": ocr_text,
                    "extraction_method": "OCR"
                })
                ocr_count += 1
            else:
                print(f"       ❌ OCR failed\n")
                results.append({
                    "filename": filename,
                    "error": "OCR extraction failed"
                })
                failed_count += 1
        
    except Exception as e:
        print(f"   └─ ❌ Error: {e}\n")
        results.append({
            "filename": filename,
            "error": str(e)
        })
        failed_count += 1

# ============================================
# SAVE RESULTS
# ============================================
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("=" * 50)
print(f"✅ PHASE 1 COMPLETE!")
print(f"   └─ Standard extraction: {standard_count} PDFs")
print(f"   └─ OCR extraction: {ocr_count} PDFs")
print(f"   └─ Failed: {failed_count} PDFs")
print(f"   └─ Total processed: {len(results)} PDFs")
print(f"   └─ Saved to: {OUTPUT_FILE}")
print("=" * 50)
print("\n   Next step: phase2_clean.py")