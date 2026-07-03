"""Agent route.

Modular router around the full LangGraph RAG pipeline (expand → retrieve →
generate). This is the same behaviour as the top-level /query endpoint, exposed
under /agent for callers that prefer the namespaced, router-based API surface.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agentic.graph import run_rag_graph
from backend.core import ollama_client, qdrant_client

router = APIRouter(prefix="/agent", tags=["agent"])


class AgentRequest(BaseModel):
    query: str
    context_limit: int = 5
    temperature: float = 0.2


@router.post("/query")
def agent_query(request: AgentRequest) -> dict:
    """Run the agentic RAG pipeline and return an answer with sources."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="The query field must not be empty.")

    if not qdrant_client.check_qdrant_health():
        raise HTTPException(status_code=503, detail="Qdrant is unavailable.")
    if not ollama_client.check_ollama_health():
        raise HTTPException(status_code=503, detail="Ollama is unavailable.")

    result = run_rag_graph(
        user_query=request.query,
        context_limit=request.context_limit,
        temperature=request.temperature,
    )

    return {
        "status": "success",
        "query": request.query,
        "answer": result.get("answer", ""),
        "expanded_queries": result.get("expanded_queries", []),
        "sources": result.get("sources", []),
    }
