import json
import os
from pathlib import Path
from typing import List, Dict, Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

INPUT_FILE = "backend/data/cleaned/phase2_cleaned.json"
OUTPUT_FILE = "backend/data/chunks/phase3_chunks.json"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)


def validate_parameters(chunk_size: int, overlap: int) -> bool:
    if chunk_size <= 0:
        print("❌ Error: CHUNK_SIZE must be positive")
        return False
    
    if overlap < 0:
        print("❌ Error: CHUNK_OVERLAP cannot be negative")
        return False
    
    if overlap >= chunk_size:
        print("❌ Warning: CHUNK_OVERLAP should be less than CHUNK_SIZE")
        return False
    
    return True


def split_into_chunks(text: str, chunk_size: int, overlap: int) -> List[str]:
    if not text or not text.strip():
        return []
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=[
            "\n\n",
            "\n",
            ". ",
            " ",
            ""
        ]
    )
    
    chunks = splitter.split_text(text)
    return chunks


def process_documents(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    all_chunks = []
    
    for doc_idx, doc in enumerate(documents, 1):
        if "content" not in doc or "filename" not in doc:
            print(f"⚠️  Skipping document {doc_idx}: Missing 'content' or 'filename' field")
            continue
        
        content = doc["content"]
        
        if not isinstance(content, str):
            print(f"⚠️  Skipping document '{doc['filename']}': Content is not text")
            continue
        
        chunks = split_into_chunks(content, CHUNK_SIZE, CHUNK_OVERLAP)
        
        if not chunks:
            print(f"⚠️  Skipping '{doc['filename']}': No chunks created")
            continue
        
        for chunk_idx, chunk_text in enumerate(chunks):
            chunk_obj = {
                "chunk_id": f"{doc['filename']}_chunk_{chunk_idx}",
                "filename": doc["filename"],
                "chunk_index": chunk_idx,
                "total_chunks": len(chunks),
                "content": chunk_text,
                "char_count": len(chunk_text),
                "word_count": len(chunk_text.split())
            }
            
            if "metadata" in doc:
                chunk_obj["metadata"] = doc["metadata"]
            
            all_chunks.append(chunk_obj)
        
        print(f"✓ {doc['filename']}: {len(chunks)} chunks created")
    
    return all_chunks


def main():
    try:
        print("🔍 Validating parameters...")
        if not validate_parameters(CHUNK_SIZE, CHUNK_OVERLAP):
            return
        print("✓ Parameters are valid\n")
        
        if not os.path.exists(INPUT_FILE):
            print(f"❌ Error: Input file not found: {INPUT_FILE}")
            return
        
        print(f"📂 Loading documents from {INPUT_FILE}...")
        with open(INPUT_FILE, "r", encoding="utf-8") as f:
            documents = json.load(f)
        
        if not isinstance(documents, list):
            print("❌ Error: Input file must contain a JSON array of documents")
            return
        
        print(f"✓ Loaded {len(documents)} documents\n")
        
        print("🔄 Creating chunks using RECURSIVE CHARACTER SPLITTER...\n")
        all_chunks = process_documents(documents)
        
        if not all_chunks:
            print("❌ Error: No chunks were generated")
            return
        
        print(f"\n💾 Saving chunks to {OUTPUT_FILE}...")
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(all_chunks, f, ensure_ascii=False, indent=2)
        
        print(f"\n{'='*60}")
        print(f"✅ SUCCESS - CHUNKING COMPLETE!")
        print(f"{'='*60}")
        print(f"Total chunks created: {len(all_chunks)}")
        print(f"Chunk size: {CHUNK_SIZE} characters")
        print(f"Chunk overlap: {CHUNK_OVERLAP} characters")
        
        total_chars = sum(c["char_count"] for c in all_chunks)
        total_words = sum(c["word_count"] for c in all_chunks)
        avg_chunk_size = total_chars / len(all_chunks) if all_chunks else 0
        
        print(f"Total characters: {total_chars:,}")
        print(f"Total words: {total_words:,}")
        print(f"Average chunk size: {avg_chunk_size:.0f} characters")
        print(f"\n📍 Output saved to: {OUTPUT_FILE}")
        
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in input file: {e}")
    except IOError as e:
        print(f"❌ Error reading/writing file: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()