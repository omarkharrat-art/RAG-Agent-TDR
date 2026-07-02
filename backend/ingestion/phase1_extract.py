import sys
import pytesseract
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

# ============================================
# CONFIGURATION
# ============================================
INPUT_FOLDER = "backend/data/raw"
OUTPUT_FILE = "backend/data/extracted/phase1_extracted.json"
OCR_DPI = 300
MIN_CHARS_THRESHOLD = 200

os.makedirs("backend/data/extracted", exist_ok=True)

# ============================================
# OCR EXTRACTION FUNCTION
# ============================================
def extract_with_ocr(filepath):
    """Extract text from PDF using OCR."""
    try:
        doc = fitz.open(filepath)
        full_text = ""
        
        for page_num, page in enumerate(doc, 1):
            try:
                pix = page.get_pixmap(matrix=fitz.Matrix(OCR_DPI/72, OCR_DPI/72))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                # Use the path we set above
                ocr_text = pytesseract.image_to_string(img)
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