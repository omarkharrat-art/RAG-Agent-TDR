"""Chat conversation endpoints: persistence + RAG-backed replies.

A conversation groups an ordered list of messages. Posting a user message
runs the RAG pipeline, stores both the user turn and the assistant turn
(with its sources and a short 'reflection' note), and returns the reply.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agentic.graph import run_rag_graph
from backend.api import chat_store
from backend.core import qdrant_client, ollama_client

router = APIRouter(prefix="/conversations", tags=["chat"])


class NewConversation(BaseModel):
    title: str | None = None


class NewMessage(BaseModel):
    query: str
    context_limit: int = 5
    temperature: float = 0.2


def _title_from_query(query: str, max_len: int = 48) -> str:
    q = " ".join(query.strip().split())
    return q if len(q) <= max_len else q[: max_len - 1].rstrip() + "…"


@router.post("")
def create_conversation(body: NewConversation) -> dict:
    title = (body.title or "").strip() or "Nouvelle conversation"
    return chat_store.create_conversation(title)


@router.get("")
def list_conversations() -> list[dict]:
    return chat_store.list_conversations()


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str) -> dict:
    conv = chat_store.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return conv


@router.delete("/{conversation_id}")
def delete_conversation(conversation_id: str) -> dict:
    if not chat_store.delete_conversation(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"status": "deleted", "id": conversation_id}


@router.post("/{conversation_id}/messages")
def post_message(conversation_id: str, body: NewMessage) -> dict:
    query = body.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="The query field must not be empty.")

    conv = chat_store.get_conversation(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    if not qdrant_client.check_qdrant_health():
        raise HTTPException(status_code=503, detail="Qdrant is unavailable.")
    if not ollama_client.check_ollama_health():
        raise HTTPException(status_code=503, detail="Ollama is unavailable.")

    # Persist the user's turn first.
    user_msg = chat_store.add_message(conversation_id, "user", query)

    # Auto-title the conversation from its first user message.
    is_first = len(conv["messages"]) == 0
    if is_first and conv["title"] == "Nouvelle conversation":
        chat_store.rename_conversation(conversation_id, _title_from_query(query))

    # Run the RAG pipeline.
    result = run_rag_graph(
        user_query=query,
        context_limit=body.context_limit,
        temperature=body.temperature,
    )
    answer = result.get("answer", "")
    sources = result.get("sources", [])
    expanded = result.get("expanded_queries", [])
    n_chunks = len(result.get("context_chunks", []))

    # Short "agentic" note surfaced in the UI reflection banner.
    reflection = (
        f"Requête reformulée en {len(expanded)} variantes · "
        f"{n_chunks} TdR consultés"
    )

    assistant_msg = chat_store.add_message(
        conversation_id, "assistant", answer, sources=sources, reflection=reflection
    )

    return {
        "conversation_id": conversation_id,
        "title": chat_store.get_conversation(conversation_id)["title"],
        "user_message": user_msg,
        "assistant_message": assistant_msg,
    }
