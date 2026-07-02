import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core import config, qdrant_client, ollama_client
from backend.agentic.graph import run_rag_graph


def preflight() -> bool:
    if not qdrant_client.check_qdrant_health():
        print("❌ Qdrant is not reachable.")
        return False

    try:
        client = qdrant_client.get_qdrant_client()
        info = client.get_collection(config.COLLECTION_NAME)
        if info.points_count == 0:
            print("❌ Collection is empty. Run phase4_embed.py first.")
            return False
        print(f"📊 {info.points_count} vectors indexed.")
    except Exception as e:
        print(f"❌ Collection error: {e}")
        return False

    if not ollama_client.check_ollama_health():
        print("❌ Ollama is not running.")
        return False

    return True


def print_result(result: dict) -> None:
    print("\n" + "=" * 60)
    print("💬 ANSWER (LangGraph + LangChain)")
    print("=" * 60)
    print(result["answer"])

    if result.get("expanded_queries"):
        print("\n" + "-" * 60)
        print("🔍 Expanded queries:")
        for i, q in enumerate(result["expanded_queries"], 1):
            print(f"   {i}. {q}")

    if result.get("sources"):
        print("\n" + "-" * 60)
        print("📎 Retrieved sources:")
        for i, src in enumerate(result["sources"], 1):
            print(
                f"   {i}. {src['filename']} "
                f"(chunk {src['chunk_index']}, score {src['score']:.4f})"
            )
    print("=" * 60 + "\n")


def main() -> int:
    print("=" * 60)
    print("🕸️  LANGGRAPH RAG PIPELINE")
    print("=" * 60)

    if not preflight():
        return 1

    if len(sys.argv) > 1:
        result = run_rag_graph(" ".join(sys.argv[1:]))
        print_result(result)
        return 0

    print("\nEnter your question. Type 'exit' to quit.\n")

    while True:
        try:
            q = input("Your question: ").strip()
            if not q:
                continue
            if q.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break
            result = run_rag_graph(q)
            print_result(result)
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())