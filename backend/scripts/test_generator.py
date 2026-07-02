import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core import config, qdrant_client, ollama_client
from backend.agentic.generator import rag_query


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
        return False

    if not ollama_client.check_ollama_health():
        print("❌ Ollama is not running. Start it with: ollama serve")
        return False

    return True


def print_result(result: dict) -> None:
    print("\n" + "=" * 60)
    print("💬 ANSWER")
    print("=" * 60)
    print(result["answer"])

    if result["sources"]:
        print("\n" + "-" * 60)
        print("📎 Sources used:")
        for i, src in enumerate(result["sources"], 1):
            print(
                f"   {i}. {src['filename']} "
                f"(chunk {src['chunk_index']}, score {src['score']:.4f})"
            )
    print("=" * 60 + "\n")


def run_once(query: str) -> None:
    result = rag_query(query, context_limit=5, temperature=0.2)
    print_result(result)


def main() -> int:
    print("=" * 60)
    print("🤖 TDR RAG GENERATOR")
    print("=" * 60)

    if not preflight():
        return 1

    # Command line: python backend/scripts/test_generator.py your question here
    if len(sys.argv) > 1:
        run_once(" ".join(sys.argv[1:]))
        return 0

    print("\nEnter your question. Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            q = input("Your question: ").strip()
            if not q:
                continue
            if q.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break
            run_once(q)
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())