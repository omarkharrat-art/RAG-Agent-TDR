import os
import sys

# Fix Unicode output on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Base Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

# Qdrant Vector DB Settings
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "tdr_documents")

# Embedding Settings
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "ibm-granite/granite-embedding-97m-multilingual-r2")
VECTOR_SIZE = int(os.getenv("VECTOR_SIZE", "384"))

# Ollama LLM Settings
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")

# Logging
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"


def validate_config() -> bool:
    """Validates that all required services are reachable and configured.
    
    Checks:
    - Qdrant vector database connectivity
    - Ollama LLM service connectivity
    - Configuration values are set
    
    Returns:
        True if all checks pass, False otherwise.
        
    Raises:
        RuntimeError if critical services are unreachable.
    """
    from backend.core.ollama_client import check_ollama_health
    from backend.core.qdrant_client import check_qdrant_health
    
    print("\n" + "="*60)
    print("🔧 Validating Configuration...")
    print("="*60)
    
    # Check configuration values
    print(f"\n📋 Configuration:")
    print(f"   Qdrant: {QDRANT_HOST}:{QDRANT_PORT}")
    print(f"   Collection: {COLLECTION_NAME}")
    print(f"   Embedding Model: {EMBEDDING_MODEL}")
    print(f"   Ollama URL: {OLLAMA_URL}")
    print(f"   Ollama Model: {OLLAMA_MODEL}")
    print(f"   Vector Size: {VECTOR_SIZE}")
    
    # Check Qdrant health
    print(f"\n🔍 Checking Qdrant...")
    if not check_qdrant_health():
        raise RuntimeError(
            f"❌ Qdrant unreachable at {QDRANT_HOST}:{QDRANT_PORT}\n"
            f"   Make sure Qdrant is running: docker run -p 6333:6333 qdrant/qdrant"
        )
    print(f"   ✅ Qdrant is healthy")
    
    # Check Ollama health
    print(f"\n🔍 Checking Ollama...")
    if not check_ollama_health():
        raise RuntimeError(
            f"❌ Ollama unreachable at {OLLAMA_URL}\n"
            f"   Make sure Ollama is running: ollama serve"
        )
    print(f"   ✅ Ollama is healthy")
    
    print("\n" + "="*60)
    print("✅ All services are healthy!")
    print("="*60 + "\n")
    
    return True


def get_config_summary() -> dict:
    """Returns a dictionary with all configuration values.
    
    Useful for logging or debugging.
    
    Returns:
        Dictionary with all config parameters.
    """
    return {
        "qdrant_host": QDRANT_HOST,
        "qdrant_port": QDRANT_PORT,
        "collection_name": COLLECTION_NAME,
        "embedding_model": EMBEDDING_MODEL,
        "vector_size": VECTOR_SIZE,
        "ollama_url": OLLAMA_URL,
        "ollama_model": OLLAMA_MODEL,
        "debug_mode": DEBUG_MODE,
    }