import json
import os
import torch
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct


INPUT_FILE = "backend/data/chunks/phase3_chunks.json"
COLLECTION_NAME = "tdr_documents"
VECTOR_SIZE = 384  
MODEL_NAME = "ibm-granite/granite-embedding-97m-multilingual-r2"  

print("=" * 60)
print("🚀 PHASE 4: EMBEDDING WITH GRANITE MULTILINGUAL MODEL")
print("=" * 60)


print("\n🔗 Connecting to Qdrant...")
try:
    client = QdrantClient(host="localhost", port=6333)
    print("✅ Connected to Qdrant!\n")
except Exception as e:
    print(f"❌ Failed to connect to Qdrant: {e}")
    exit(1)


print(f"🔄 Setting up collection '{COLLECTION_NAME}'...")
existing = [c.name for c in client.get_collections().collections]

if COLLECTION_NAME in existing:
    client.delete_collection(COLLECTION_NAME)
    print(f"   └─ Deleted old collection (was using MiniLM)")

client.create_collection(
    collection_name=COLLECTION_NAME,
    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
)
print(f"   └─ Created new collection (size {VECTOR_SIZE})\n")


device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"🖥️ Using device: {device}")
if device == 'cuda':
    print(f"   └─ GPU: {torch.cuda.get_device_name(0)}")


print(f"\n🤖 Loading embedding model: {MODEL_NAME}")
print("   └─ This model supports French, English, and Arabic!")
print("   └─ First download may take 30-60 seconds...")

model = SentenceTransformer(MODEL_NAME, device=device)
print("   └─ Model ready!\n")


print(f"📖 Loading chunks from {INPUT_FILE}...")
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    chunks = json.load(f)

print(f"   └─ Loaded {len(chunks)} chunks\n")


print(f"⚡ Generating embeddings with Granite multilingual model...")
print("   └─ This may take 2-3 minutes on GPU\n")

texts = [chunk["content"] for chunk in chunks]
vectors = model.encode(texts, show_progress_bar=True)

print(f"\n   └─ Generated {len(vectors)} embeddings\n")

print(f"📤 Uploading to Qdrant...")

BATCH_SIZE = 100
points_batch = []
total_uploaded = 0

for i, chunk in enumerate(chunks):
    point = PointStruct(
        id=i,
        vector=vectors[i].tolist(),
        payload={
            "chunk_id": chunk["chunk_id"],
            "filename": chunk["filename"],
            "chunk_index": chunk["chunk_index"],
            "content": chunk["content"]
        }
    )
    points_batch.append(point)
    
    if len(points_batch) >= BATCH_SIZE:
        client.upsert(collection_name=COLLECTION_NAME, points=points_batch)
        total_uploaded += len(points_batch)
        print(f"   ✅ Uploaded {total_uploaded} / {len(chunks)} chunks")
        points_batch = []

if points_batch:
    client.upsert(collection_name=COLLECTION_NAME, points=points_batch)
    print(f"   ✅ Uploaded {len(chunks)} / {len(chunks)} chunks")


count = client.get_collection(COLLECTION_NAME).points_count
print(f"\n" + "=" * 60)
print(f"✅ SUCCESS! {count} vectors stored in Qdrant")
print(f"   └─ Model: {MODEL_NAME}")
print(f"   └─ Vector size: {VECTOR_SIZE}")
print(f"   └─ Device: {device}")
print("=" * 60)
print("\n🎯 Your RAG is now using a multilingual model!")
print("   Expected score improvement: 0.456 → 0.65 - 0.75")