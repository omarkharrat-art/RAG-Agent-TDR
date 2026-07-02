from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
import torch


MODEL_NAME = "ibm-granite/granite-embedding-97m-multilingual-r2"
COLLECTION_NAME = "tdr_documents"

print("🔗 Connecting to Qdrant...")
client = QdrantClient(host="localhost", port=6333)
print("✅ Connected!\n")

device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"🖥️ Using device: {device}")

print("🤖 Loading embedding model...")
model = SentenceTransformer(MODEL_NAME, device=device)
print("✅ Model ready!\n")

try:
    collection = client.get_collection(COLLECTION_NAME)
    vector_count = collection.points_count
    print(f"📊 Collection: {COLLECTION_NAME}")
    print(f"   └─ Vectors indexed: {vector_count}\n")
except Exception as e:
    print(f"❌ Collection not found: {e}")
    exit(1)

# Search loop
while True:
    query = input("🔍 Enter search query (or 'quit' to exit): ").strip()
    
    if query.lower() in ['quit', 'exit', 'q']:
        print("\n👋 Goodbye!")
        break
    
    if not query:
        print("⚠️  Please enter a search query\n")
        continue
    
    print(f"\n🔍 Searching for: '{query}'\n")
    
    query_vector = model.encode(query).tolist()
    
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=5
    ).points
    
    if not results:
        print("❌ No results found\n")
        continue
    
    for i, result in enumerate(results, 1):
        filename = result.payload.get('filename', 'Unknown')
        content = result.payload.get('content', '')[:200]
        score = result.score
        
        print(f"   {i}. [{score:.3f}] {filename}")
        print(f"      Preview: {content}...\n")