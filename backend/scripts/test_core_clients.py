import sys
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core import config, qdrant_client, ollama_client


def test_clients() -> int:
    print("=" * 60)
    print("🔍 VERIFYING CORE CLIENTS")
    print("=" * 60)

    print("\n⚙️ Settings:")
    print(f"   - Qdrant Host:    {config.QDRANT_HOST}")
    print(f"   - Qdrant Port:    {config.QDRANT_PORT}")
    print(f"   - Collection:     {config.COLLECTION_NAME}")
    print(f"   - Ollama URL:     {config.OLLAMA_URL}")
    print(f"   - Ollama Model:   {config.OLLAMA_MODEL}")

    all_ok = True

    print("\n📡 Qdrant Connection Check:")
    if qdrant_client.check_qdrant_health():
        print("   ✅ Successfully connected to Qdrant!")
        try:
            client = qdrant_client.get_qdrant_client()
            info = client.get_collection(config.COLLECTION_NAME)
            print(f"   📊 Collection '{config.COLLECTION_NAME}': {info.points_count} vectors")
        except Exception as e:
            print(f"   ⚠️ Collection '{config.COLLECTION_NAME}' not found: {e}")
            print("      Run phase4_embed.py to index documents.")
    else:
        print("   ❌ Could not connect to Qdrant. Make sure Docker is running.")
        all_ok = False

    print("\n🦙 Ollama Connection Check:")
    if ollama_client.check_ollama_health():
        print("   ✅ Successfully connected to Ollama!")
        print("   💬 Testing text generation...")
        test_response = ollama_client.query_ollama("Respond with exactly: 'Ollama is alive!'")
        if test_response:
            print(f"      Response: '{test_response}'")
        else:
            print("   ❌ Ollama responded but returned empty text.")
            all_ok = False
    else:
        print("   ❌ Could not connect to Ollama. Run: ollama serve")
        all_ok = False

    print("=" * 60)
    if all_ok:
        print("✅ All core clients are healthy!")
    else:
        print("❌ One or more core clients failed.")
    print("=" * 60)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(test_clients())