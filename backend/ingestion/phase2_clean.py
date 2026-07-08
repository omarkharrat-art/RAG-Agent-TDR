import sys
import json
import re
import os

# Fix Unicode output on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Now reads from phase0_classified.json (TDRs only, filtered by phase0_classifier.py)
INPUT_FILE  = "backend/data/extracted/phase0_classified.json"
OUTPUT_FILE = "backend/data/cleaned/phase2_cleaned.json"

os.makedirs("backend/data/cleaned", exist_ok=True)

_VOWELS = r"aeiouyàâäéèêëïîôöûüù"


def strip_ocr_garbage(text: str) -> str:
    """Remove OCR artifacts produced by scanned pages.

    Scanned TdRs (especially their tables of contents) contain dotted leaders
    (".....") and small fonts that OCR misreads as runs of repeated or
    consonant-only characters (rrrr, cccc, "mn | crr | urr"). These pollute
    retrieval and answers. This strips them line by line while preserving real
    prose:
      - collapse dotted/ellipsis/underscore leaders and 4+ repeated chars;
      - remove absurdly long alphabetic tokens (OCR runs, 22+ chars);
      - drop a whole line if it is mostly vowel-poor gibberish.
    """
    out = []
    for ln in text.split("\n"):
        ln = re.sub(r"[.\-_·•…]{2,}", " ", ln)
        ln = re.sub(r"(\S)\1{3,}", " ", ln)
        ln = re.sub(rf"[A-Za-z{_VOWELS}ç]{{22,}}", " ", ln)

        letters = re.findall(rf"[A-Za-z{_VOWELS}ç]", ln)
        vowels = re.findall(rf"[{_VOWELS}]", ln, re.I)
        if len(letters) >= 10 and len(vowels) / len(letters) < 0.28:
            continue

        words = re.findall(rf"[A-Za-z{_VOWELS}ç]+", ln)
        if len(words) >= 4:
            novowel = sum(1 for w in words if not re.search(rf"[{_VOWELS}]", w, re.I))
            if novowel / len(words) > 0.4:
                continue

        ln = re.sub(r"(\s*\|\s*){2,}", " | ", ln)
        ln = re.sub(r"[ \t]{2,}", " ", ln).strip()
        if ln:
            out.append(ln)
    return "\n".join(out)


def clean_text(text):
    text = text.replace("\r", "\n")
    text = strip_ocr_garbage(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" \n", "\n", text)
    text = text.strip()
    return text

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    documents = json.load(f)

print("=" * 50)
print("PHASE 2: TEXT CLEANING")
print("=" * 50)
print(f"\nLoaded {len(documents)} classified TDR documents\n")

cleaned_documents = []

for doc in documents:
    # Skip documents without content (extraction errors)
    if "error" in doc or not doc.get("content"):
        print(f"SKIP {doc['filename']}: no content")
        continue

    original_length = len(doc["content"])
    cleaned_content = clean_text(doc["content"])
    cleaned_length = len(cleaned_content)

    cleaned_documents.append({
        "filename": doc["filename"],
        "content": cleaned_content,
        "extraction_method": doc.get("extraction_method", "standard")
    })

    print(f"OK   {doc['filename']}: {original_length} -> {cleaned_length} chars")

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(cleaned_documents, f, ensure_ascii=False, indent=2)

print(f"\nDone! Saved {len(cleaned_documents)} cleaned TDR documents to {OUTPUT_FILE}")
print("\n   Next step: phase3_chunk.py")