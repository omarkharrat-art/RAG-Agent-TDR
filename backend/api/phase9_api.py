import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.agentic.graph import run_rag_graph
from backend.core import config, qdrant_client, ollama_client
from backend.api import chat_store
from backend.api.routes import agent, chat, documents, filters, search


class QueryRequest(BaseModel):
    query: str
    context_limit: int = 5
    temperature: float = 0.2
    document: str | None = None  # restrict retrieval to this exact filename


class EvaluateRequest(QueryRequest):
    """Same as a query, but the response is additionally graded against a
    ground truth derived from the retrieved context. Intended for offline
    evaluation / QA, NOT for the normal user-facing request path."""
    pass


app = FastAPI(
    title="Agentic RAG Backend",
    description="Backend API for TDR retrieval and generation.",
    version="0.1.0",
)

# Allow the React dev server / containerized frontend to call the API.
# Tighten allow_origins for production if the frontend is served elsewhere.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    # Create the chat history tables if they don't exist yet.
    chat_store.init_db()


# Modular routers: /search (retrieval only), /filters (corpus metadata),
# /agent (full RAG pipeline), /conversations (persisted chat history). The
# top-level /query and /evaluate endpoints below are kept for compatibility.
app.include_router(search.router)
app.include_router(filters.router)
app.include_router(agent.router)
app.include_router(chat.router)
app.include_router(documents.router)


def _require_services() -> None:
    """Raise 503 if a backing service is unavailable."""
    if not qdrant_client.check_qdrant_health():
        raise HTTPException(status_code=503, detail="Qdrant is unavailable.")
    if not ollama_client.check_ollama_health():
        raise HTTPException(status_code=503, detail="Ollama is unavailable.")


@app.get("/")
def root() -> dict:
    return {"message": "Agentic RAG backend is running."}


@app.get("/health")
def health() -> dict:
    from backend.agentic.retriever import is_using_fallback

    qdrant_ok = qdrant_client.check_qdrant_health()
    ollama_ok = ollama_client.check_ollama_health()
    using_fallback = is_using_fallback()

    # Fallback embeddings mean retrieval is effectively broken, so report
    # the service as degraded even if Qdrant/Ollama are reachable.
    status = "healthy" if (qdrant_ok and ollama_ok and not using_fallback) else "unhealthy"
    return {
        "status": status,
        "qdrant": qdrant_ok,
        "ollama": ollama_ok,
        "embeddings": "fallback (non-semantic)" if using_fallback else "ok",
        "config": config.get_config_summary(),
    }


@app.post("/query")
def query(request: QueryRequest) -> dict:
    """User-facing RAG endpoint: retrieve context and generate an answer.

    Deliberately does NOT self-grade the answer. Grading requires a second
    LLM call and doubles latency, and comparing the answer to the context it
    was generated from is not a meaningful correctness signal. Use /evaluate
    for that instead.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="The query field must not be empty.")

    _require_services()

    result = run_rag_graph(
        user_query=request.query,
        context_limit=request.context_limit,
        temperature=request.temperature,
        filename=request.document,
    )

    return {
        "status": "success",
        "query": request.query,
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        # Agentic loop diagnostics: how many retry cycles ran and the
        # reflection verdict, so the UI can surface the self-correction.
        "retries": result.get("retries", 0),
        "reflection": result.get("reflection", {}),
    }


def _derive_ground_truth(context_chunks: list[dict]) -> str | None:
    """Pick a reference answer from retrieved chunks.

    Prefers the highest-scoring chunk carrying an explicit `answer` field;
    otherwise falls back to the top chunk's content.
    """
    if not context_chunks:
        return None

    best_labeled = None
    for c in context_chunks:
        if c.get("answer"):
            if best_labeled is None or c.get("score", 0) > best_labeled.get("score", 0):
                best_labeled = c

    if best_labeled:
        return best_labeled.get("answer") or best_labeled.get("content")
    return context_chunks[0].get("content")


def _grade_answer(question: str, llm_answer: str, ground_truth: str) -> dict:
    """Use the LLM to compare an answer against a ground truth."""
    compare_system = (
        "You are an objective evaluator. Given a model-generated answer and a ground-truth answer, "
        "decide whether the model answer is correct, complete, and faithful to the ground truth. "
        "Respond ONLY with a compact JSON object with two keys: \"is_correct\" (true/false) and "
        "\"correction\" (a brief correction if false, or an empty string if true)."
    )
    compare_prompt = (
        f"Model answer:\n{llm_answer}\n\nGround truth:\n{ground_truth}\n\n"
        f"Question: {question}\n\n"
        "Instructions: Decide if the model answer is correct relative to the ground truth. "
        "If correct, return {\"is_correct\": true, \"correction\": \"\"}. "
        "If incorrect or incomplete, return {\"is_correct\": false, \"correction\": \"<brief correction>\"}. "
        "Return only valid JSON."
    )

    comp_resp = ollama_client.query_ollama(
        prompt=compare_prompt,
        system_prompt=compare_system,
        temperature=0.0,
    )

    try:
        parsed = json.loads(comp_resp)
        return {
            "is_correct": bool(parsed.get("is_correct")),
            "correction": parsed.get("correction", ""),
        }
    except Exception:
        # Parsing failed: leave correctness undecided, surface the raw text.
        return {"is_correct": None, "correction": comp_resp.strip()}


@app.post("/evaluate")
def evaluate(request: EvaluateRequest) -> dict:
    """Offline/QA endpoint: run the RAG pipeline AND grade the answer against
    a ground truth derived from the retrieved context."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="The query field must not be empty.")

    _require_services()

    result = run_rag_graph(
        user_query=request.query,
        context_limit=request.context_limit,
        temperature=request.temperature,
    )
    llm_answer = result.get("answer", "")
    context_chunks = result.get("context_chunks", [])

    ground_truth = _derive_ground_truth(context_chunks)
    grade = {"is_correct": None, "correction": ""}
    if ground_truth:
        grade = _grade_answer(request.query, llm_answer, ground_truth)

    return {
        "status": "success",
        "query": request.query,
        "answer": llm_answer,
        "ground_truth": ground_truth,
        "is_correct": grade["is_correct"],
        "correction": grade["correction"],
        "sources": result.get("sources", []),
    }
