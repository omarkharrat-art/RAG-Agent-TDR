import json
import os
import sys
from typing import List, Dict, Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

# Fix Unicode output on Windows terminals (cp1252 -> utf-8). Without this,
# the emoji in this script's print() calls crash it when run as a subprocess.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

INPUT_FILE = "backend/data/cleaned/phase2_cleaned.json"
OUTPUT_FILE = "backend/data/chunks/phase3_chunks.json"

# ── Hierarchical ("parent–child" / small-to-big) chunking ────────────
#
# We build TWO levels per document:
#   • Parent chunks  — large sections (~1500 chars) that keep tables, lists
#     and multi-line structures whole. These are what we hand to the LLM.
#   • Child chunks   — small slices (~400 chars) of each parent. These are
#     what we embed and search on, because a short, focused slice embeds far
#     more sharply than a big diluted block.
#
# The output is a flat list of CHILD chunks; each child carries its parent's
# id and full text (parent_content). Retrieval matches on the child vector,
# then returns the parent_content so the model sees complete context.
PARENT_CHUNK_SIZE = 1500
PARENT_CHUNK_OVERLAP = 200
CHILD_CHUNK_SIZE = 400
CHILD_CHUNK_OVERLAP = 80

_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)


def validate_parameters() -> bool:
    for size, overlap, name in (
        (PARENT_CHUNK_SIZE, PARENT_CHUNK_OVERLAP, "parent"),
        (CHILD_CHUNK_SIZE, CHILD_CHUNK_OVERLAP, "child"),
    ):
        if size <= 0:
            print(f"❌ Error: {name} chunk size must be positive")
            return False
        if overlap < 0:
            print(f"❌ Error: {name} overlap cannot be negative")
            return False
        if overlap >= size:
            print(f"❌ Error: {name} overlap must be smaller than its chunk size")
            return False
    if CHILD_CHUNK_SIZE > PARENT_CHUNK_SIZE:
        print("❌ Error: child chunks must be smaller than parent chunks")
        return False
    return True


def build_splitters():
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=PARENT_CHUNK_SIZE,
        chunk_overlap=PARENT_CHUNK_OVERLAP,
        separators=_SEPARATORS,
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHILD_CHUNK_SIZE,
        chunk_overlap=CHILD_CHUNK_OVERLAP,
        separators=_SEPARATORS,
    )
    return parent_splitter, child_splitter


def chunk_document(
    doc: Dict[str, Any],
    parent_splitter: RecursiveCharacterTextSplitter,
    child_splitter: RecursiveCharacterTextSplitter,
) -> List[Dict[str, Any]]:
    """Split one document into child chunks, each linked to its parent."""
    content = doc["content"]
    filename = doc["filename"]

    parents = parent_splitter.split_text(content)
    children: List[Dict[str, Any]] = []
    global_child_index = 0

    for p_idx, parent_text in enumerate(parents):
        parent_id = f"{filename}_parent_{p_idx}"
        for child_text in child_splitter.split_text(parent_text):
            if not child_text.strip():
                continue
            child = {
                "chunk_id": f"{filename}_p{p_idx}_c{global_child_index}",
                "filename": filename,
                "chunk_index": global_child_index,
                "parent_id": parent_id,
                "parent_index": p_idx,
                "total_parents": len(parents),
                # `content` is the small child text that gets embedded/searched.
                "content": child_text,
                # `parent_content` is the large block returned to the LLM.
                "parent_content": parent_text,
                "char_count": len(child_text),
                "word_count": len(child_text.split()),
            }
            if "metadata" in doc:
                child["metadata"] = doc["metadata"]
            children.append(child)
            global_child_index += 1

    return children


def process_documents(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    parent_splitter, child_splitter = build_splitters()
    all_children: List[Dict[str, Any]] = []
    parent_total = 0

    for doc_idx, doc in enumerate(documents, 1):
        if "content" not in doc or "filename" not in doc:
            print(f"⚠️  Skipping document {doc_idx}: missing 'content' or 'filename'")
            continue
        if not isinstance(doc["content"], str) or not doc["content"].strip():
            print(f"⚠️  Skipping '{doc.get('filename', '?')}': empty/non-text content")
            continue

        children = chunk_document(doc, parent_splitter, child_splitter)
        if not children:
            print(f"⚠️  Skipping '{doc['filename']}': no chunks created")
            continue

        parents_here = children[-1]["total_parents"]
        parent_total += parents_here
        all_children.extend(children)
        print(f"✓ {doc['filename']}: {parents_here} parents → {len(children)} children")

    print(f"\n🌳 Parents total: {parent_total}")
    return all_children


def main():
    print("🔍 Validating parameters...")
    if not validate_parameters():
        return
    print("✓ Parameters are valid\n")

    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: input file not found: {INPUT_FILE}")
        return

    print(f"📂 Loading documents from {INPUT_FILE}...")
    try:
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            documents = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Error: invalid JSON in input file: {e}")
        return

    if not isinstance(documents, list):
        print("❌ Error: input file must contain a JSON array of documents")
        return

    print(f"✓ Loaded {len(documents)} documents\n")
    print("🔄 Creating HIERARCHICAL (parent → child) chunks...\n")

    all_children = process_documents(documents)
    if not all_children:
        print("❌ Error: no chunks were generated")
        return

    print(f"\n💾 Saving chunks to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_children, f, ensure_ascii=False, indent=2)

    total_chars = sum(c["char_count"] for c in all_children)
    avg = total_chars / len(all_children) if all_children else 0

    print("\n" + "=" * 60)
    print("✅ SUCCESS - HIERARCHICAL CHUNKING COMPLETE!")
    print("=" * 60)
    print(f"Child chunks created: {len(all_children)}")
    print(f"Parent size: {PARENT_CHUNK_SIZE} / overlap {PARENT_CHUNK_OVERLAP}")
    print(f"Child size:  {CHILD_CHUNK_SIZE} / overlap {CHILD_CHUNK_OVERLAP}")
    print(f"Average child size: {avg:.0f} characters")
    print(f"\n📍 Output saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
