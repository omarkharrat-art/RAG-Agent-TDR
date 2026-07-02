import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core import ollama_client
from backend.agentic.query_expander import expand_query


def main() -> int:
    print("=" * 60)
    print("🔍 INTERACTIVE QUERY EXPANDER")
    print("=" * 60)

    if not ollama_client.check_ollama_health():
        print("❌ Ollama is not running. Start it with: ollama serve")
        print("   And make sure the model is pulled: ollama pull llama3.2:latest")
        return 1

    print("Type a search query and press Enter. Type 'exit' or 'quit' to stop.\n")

    while True:
        try:
            q = input("Enter query: ").strip()
            if not q:
                continue
            if q.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break

            print("🤖 Expanding...")
            expansions = expand_query(q)

            if not expansions:
                print("❌ No expansions returned.\n")
                continue

            print(f"\n✅ {len(expansions)} expanded queries:")
            for i, term in enumerate(expansions, 1):
                print(f"   {i}. {term}")
            print("\n" + "-" * 60 + "\n")

        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

    return 0


if __name__ == "__main__":
    sys.exit(main())