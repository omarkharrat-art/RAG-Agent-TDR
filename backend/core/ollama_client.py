import sys
import requests
from backend.core import config

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')


def _ollama_base_url() -> str:
    """Derive base URL from OLLAMA_URL (e.g. http://localhost:11434)."""
    url = config.OLLAMA_URL.rstrip("/")
    if url.endswith("/api/generate"):
        return url[: -len("/api/generate")]
    return url.split("/api/")[0]


def check_ollama_health() -> bool:
    """Returns True if Ollama is reachable."""
    try:
        response = requests.get(f"{_ollama_base_url()}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Ollama health check failed: {e}")
        return False


def query_ollama(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float = 0.2,
    model: str | None = None,
) -> str:
    """Send a prompt to Ollama and return the text response."""
    if model is None:
        model = config.OLLAMA_MODEL

    # Ollama's /api/generate expects sampling params under "options".
    # A top-level "temperature" key is silently ignored, so it must go here.
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
        },
    }
    if system_prompt:
        payload["system"] = system_prompt

    try:
        response = requests.post(config.OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
        result = response.json()
        return (result.get("response") or "").strip()
    except Exception as e:
        print(f"❌ Ollama query failed: {e}")
        return ""