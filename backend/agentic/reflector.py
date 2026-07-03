"""Reflection step for the agentic RAG pipeline.

Given a user question and the chunks retrieved for it, ask the LLM whether the
retrieved context is actually sufficient to answer. This is the "agentic" part:
the graph can use the verdict to decide whether to retry retrieval (with a
reformulated query) before spending an LLM call on generation.

Kept deliberately small and dependency-light — it calls Ollama directly via
core.ollama_client rather than going through LangChain.
"""

import json
import re
import sys

from backend.core.ollama_client import query_ollama

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


_SYSTEM_PROMPT = (
    "You are a strict retrieval evaluator for a Terms of Reference (TDR) "
    "question-answering system. Given a user question and some retrieved "
    "context passages, decide whether the context contains enough information "
    "to answer the question.\n"
    "Respond ONLY with a compact JSON object with two keys:\n"
    '  "sufficient" (true/false)\n'
    '  "reason" (a short explanation, one sentence)\n'
    "Do not add markdown fences or any text outside the JSON."
)


def _extract_json(text: str) -> dict | None:
    """Best-effort parse of a JSON object out of an LLM response."""
    try:
        return json.loads(text)
    except Exception:
        pass
    # Fall back to grabbing the first {...} block.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None


def reflect_on_context(
    question: str,
    chunks: list[dict],
    temperature: float = 0.0,
) -> dict:
    """Judge whether `chunks` are sufficient to answer `question`.

    Returns a dict: {"sufficient": bool, "reason": str}. On any failure it
    defaults to sufficient=True so reflection never blocks the pipeline —
    a wrong "retry" is more costly than skipping the check.
    """
    if not chunks:
        return {"sufficient": False, "reason": "No context was retrieved."}

    # Only feed the top few chunks to keep the prompt small and fast.
    context = "\n\n".join(
        f"[{i}] ({c.get('filename', 'Unknown')}) {c.get('content', '').strip()}"
        for i, c in enumerate(chunks[:5], 1)
    )

    prompt = (
        f"Question:\n{question}\n\n"
        f"Retrieved context:\n{context}\n\n"
        "Is this context sufficient to answer the question? "
        "Return only the JSON object."
    )

    raw = query_ollama(prompt=prompt, system_prompt=_SYSTEM_PROMPT, temperature=temperature)
    parsed = _extract_json(raw)

    if parsed is None or "sufficient" not in parsed:
        # Undecided → don't block generation.
        return {"sufficient": True, "reason": "Reflection undecided; proceeding."}

    return {
        "sufficient": bool(parsed.get("sufficient")),
        "reason": str(parsed.get("reason", "")),
    }
