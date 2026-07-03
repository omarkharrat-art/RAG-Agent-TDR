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


@router.post("")
def search(request: SearchRequest) -> dict:
    """Return the top matching chunks for a query, no answer generation."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="The query field must not be empty.")

    if not qdrant_client.check_qdrant_health():
        raise HTTPException(status_code=503, detail="Qdrant is unavailable.")

    chunks = retrieve_context(request.query, limit=request.limit)

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
