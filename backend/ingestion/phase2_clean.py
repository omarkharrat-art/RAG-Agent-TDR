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

def clean_text(text):
    text = text.replace("\r", "\n")
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