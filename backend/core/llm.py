"""Provider-aware LLM factory.

Switch the whole app between a local model (Ollama) and a cloud model (Groq)
with a single setting, config.LLM_PROVIDER ("ollama" | "groq"). Everything that
needs an LLM — answer generation, query expansion, the evaluator — goes through
here, so one env var controls them all.
"""

import sys

from langchain_core.messages import HumanMessage, SystemMessage

from backend.core import config

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def _ollama_base_url() -> str:
    return config.OLLAMA_URL.replace("/api/generate", "").rstrip("/")


# Cache chat models by (provider, temperature) so we don't rebuild them per call.
_cache: dict = {}


def get_chat_llm(temperature: float = 0.2):
    """Return a LangChain chat model for the currently selected provider."""
    key = (config.LLM_PROVIDER, temperature)
    if key in _cache:
        return _cache[key]

    if config.LLM_PROVIDER == "groq":
        from langchain_groq import ChatGroq

        llm = ChatGroq(
            model=config.GROQ_MODEL,
            api_key=config.GROQ_API_KEY,
            temperature=temperature,
        )
    else:
        from langchain_ollama import ChatOllama

        llm = ChatOllama(
            model=config.OLLAMA_MODEL,
            base_url=_ollama_base_url(),
            temperature=temperature,
        )

    _cache[key] = llm
    return llm


def active_model() -> str:
    """Name of the model currently in use (for logging / display)."""
    return config.GROQ_MODEL if config.LLM_PROVIDER == "groq" else config.OLLAMA_MODEL


def complete(prompt: str, system_prompt: str | None = None, temperature: float = 0.2) -> str:
    """Single-shot text completion via the active provider.

    Used where a plain string in/out is wanted (query expansion, the
    evaluator) instead of a full LangChain chain. Passes messages directly so
    literal braces in the prompt aren't treated as template variables.
    """
    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))

    try:
        resp = get_chat_llm(temperature).invoke(messages)
        return (resp.content or "").strip()
    except Exception as e:
        print(f"❌ LLM completion failed (provider={config.LLM_PROVIDER}): {e}")
        return ""


def check_llm_health() -> bool:
    """Provider-aware health check.

    - ollama: ping the local server.
    - groq: verify an API key is configured (a cheap, offline check).
    """
    if config.LLM_PROVIDER == "groq":
        return bool(config.GROQ_API_KEY)
    from backend.core.ollama_client import check_ollama_health

    return check_ollama_health()
