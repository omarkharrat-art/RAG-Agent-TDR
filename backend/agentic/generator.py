import sys
from backend.core.ollama_client import query_ollama
from backend.agentic.retriever import retrieve_context

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')


SYSTEM_PROMPT = (
    "You are an expert assistant for Terms of Reference (TDR / TdR) documents "
    "used in international development and consultancy missions.\n\n"
    "Rules:\n"
    "- Answer ONLY using the provided context chunks.\n"
    "- If the context does not contain enough information, say so clearly.\n"
    "- Do not invent facts, dates, names, or requirements.\n"
    "- The user may ask in French or English; respond in the SAME language as the question.\n"
    "- Be concise, structured, and practical.\n"
    "- At the end, list the source document filenames you used."
)


def format_context(chunks: list[dict]) -> str:
    """Format retrieved chunks into a single context block for the LLM."""
    if not chunks:
        return ""

    parts = []
    for i, chunk in enumerate(chunks, 1):
        filename = chunk.get("filename", "Unknown")
        score = chunk.get("score", 0.0)
        content = chunk.get("content", "").strip()
        parts.append(
            f"[Source {i}] File: {filename} | Score: {score:.4f}\n{content}"
        )
    return "\n\n".join(parts)


def generate_answer(
    user_query: str,
    context_chunks: list[dict],
    temperature: float = 0.2,
) -> str:
    """Generate an answer from retrieved context using Ollama."""
    if not user_query or not user_query.strip():
        return "Please provide a valid question."

    if not context_chunks:
        return (
            "I could not find relevant information in the TDR document database "
            "to answer your question."
        )

    context_block = format_context(context_chunks)

    prompt = (
        f"Context from TDR documents:\n\n"
        f"{context_block}\n\n"
        f"---\n\n"
        f"User question: {user_query.strip()}\n\n"
        f"Answer the question using only the context above."
    )

    answer = query_ollama(
        prompt=prompt,
        system_prompt=SYSTEM_PROMPT,
        temperature=temperature,
    )

    if not answer:
        return "Generation failed. Check that Ollama is running and the model is available."

    return answer


def rag_query(
    user_query: str,
    context_limit: int = 5,
    temperature: float = 0.2,
) -> dict:
    """
    Full RAG pipeline: retrieve context, then generate an answer.

    Returns:
        {
            "query": str,
            "answer": str,
            "sources": [{"filename", "chunk_index", "score"}, ...],
            "context_chunks": list[dict],
        }
    """
    print(f"\n📚 Retrieving context for: '{user_query}'")
    context_chunks = retrieve_context(user_query, limit=context_limit)

    sources = [
        {
            "filename": c.get("filename", "Unknown"),
            "chunk_index": c.get("chunk_index", 0),
            "score": c.get("score", 0.0),
        }
        for c in context_chunks
    ]

    print("✍️ Generating answer...")
    answer = generate_answer(
        user_query=user_query,
        context_chunks=context_chunks,
        temperature=temperature,
    )

    return {
        "query": user_query,
        "answer": answer,
        "sources": sources,
        "context_chunks": context_chunks,
    }