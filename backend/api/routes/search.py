"""Retrieval-only search route.

Exposes the vector-retrieval half of the RAG pipeline WITHOUT LLM generation.
Useful for inspecting retrieval quality (which chunks/scores come back for a
query) and as a lightweight semantic search endpoint that skips the slower
generation step.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agentic.retriever import retrieve_context
from backend.core import qdrant_client

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str
    limit: int = 5
    document: str | None = None  # restrict search to this filename
    expand: bool = False  # LLM query expansion — off by default for fast search


@router.post("")
def search(request: SearchRequest) -> dict:
    """Return the top matching chunks for a query, no answer generation.

    By default this skips LLM query expansion: embedding search already handles
    synonyms well, so for interactive search we send the raw query straight to
    the vector DB (one search, no Ollama round-trip) — much faster. Pass
    expand=True to opt into multi-variation retrieval.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="The query field must not be empty.")

    if not qdrant_client.check_qdrant_health():
        raise HTTPException(status_code=503, detail="Qdrant is unavailable.")

    # Passing expanded_queries=[query] bypasses the internal LLM expansion and
    # runs a single vector search instead of one per variation.
    expanded = None if request.expand else [request.query]
    chunks = retrieve_context(
        request.query,
        limit=request.limit,
        filename=request.document,
        expanded_queries=expanded,
    )

    return {
        "status": "success",
        "query": request.query,
        "count": len(chunks),
        "results": [
            {
                "filename": c.get("filename", "Unknown"),
                "chunk_index": c.get("chunk_index", 0),
                "score": c.get("score", 0.0),
                "content": c.get("content", ""),
            }
            for c in chunks
        ],
    }
