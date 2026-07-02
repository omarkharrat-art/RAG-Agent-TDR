import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core import config, qdrant_client, ollama_client
from backend.agentic.retriever import retrieve_context


def preflight() -> bool:
    if not qdrant_client.check_qdrant_health():
        print("❌ Qdrant is not reachable. Start Docker: docker compose up -d")
        return False

    try:
        client = qdrant_client.get_qdrant_client()
        info = client.get_collection(config.COLLECTION_NAME)
        if info.points_count == 0:
            print(f"❌ Collection '{config.COLLECTION_NAME}' is empty. Run phase4_embed.py first.")
            return False
        print(f"📊 Collection has {info.points_count} indexed vectors.")
    except Exception as e:
        print(f"❌ Collection '{config.COLLECTION_NAME}' not found: {e}")
        print("   Run phase4_embed.py to index documents.")
        return False

    if not ollama_client.check_ollama_health():
        print("❌ Ollama is not running. Start it with: ollama serve")
        return False

    return True


def run_query(query: str, limit: int = 3) -> None:
    print(f"\nSearch Query: '{query}'")
    print("🤖 Retrieving context chunks...")

    results = retrieve_context(query, limit=limit)

    if not results:
        print("❌ No matching chunks retrieved.")
        return

    print(f"\n✅ Retrieved {len(results)} deduplicated chunks:")
    for i, res in enumerate(results, 1):
        print(f"\n--- Result {i} (Score: {res['score']:.4f}) ---")
        print(f"File: {res['filename']} (Chunk Index: {res['chunk_index']})")
        print(f"Content snippet:\n{res['content'][:250]}...")
        print("-" * 40)


def main() -> int:
    print("=" * 60)
    print("🔍 TESTING RETRIEVER AGENT")
    print("=" * 60)

    if not preflight():
        return 1

    # Option 1: pass query on command line
    if len(sys.argv) > 1:
        run_query(" ".join(sys.argv[1:]))
        return 0

    # Option 2: type query interactively
    print("\nEnter your search query. Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            q = input("Enter query: ").strip()
            if not q:
                continue
            if q.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break
            run_query(q)
            print()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())