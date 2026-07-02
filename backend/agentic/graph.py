import sys
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama

from backend.core import config
from backend.agentic.query_expander import expand_query
from backend.agentic.retriever import retrieve_context

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# ── LangGraph state ──────────────────────────────────────────────

class RAGState(TypedDict, total=False):
    query: str
    expanded_queries: list[str]
    context_chunks: list[dict]
    sources: list[dict]
    answer: str
    context_limit: int
    temperature: float


DEFAULT_TEMPERATURE = 0.2

# ── LangChain LLM + prompt ───────────────────────────────────────

_OLLAMA_BASE_URL = config.OLLAMA_URL.replace("/api/generate", "")

# ChatOllama instances cached by temperature. temperature must be set at
# construction time (ChatOllama maps it into Ollama's `options`); passing it
# via .bind() leaks it as a raw kwarg into the underlying Client.chat(), which
# newer langchain-ollama rejects with "unexpected keyword argument 'temperature'".
_llm_cache: dict[float, ChatOllama] = {}


def _get_llm(temperature: float) -> ChatOllama:
    llm = _llm_cache.get(temperature)
    if llm is None:
        llm = ChatOllama(
            model=config.OLLAMA_MODEL,
            base_url=_OLLAMA_BASE_URL,
            temperature=temperature,
        )
        _llm_cache[temperature] = llm
    return llm

GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an expert assistant for Terms of Reference (TDR / TdR) documents "
        "used in international development and consultancy missions.\n\n"
        "Rules:\n"
        "- Answer ONLY using the provided context.\n"
        "- If the context is insufficient, say so clearly.\n"
        "- Do not invent facts.\n"
        "- Respond in the SAME language as the user's question.\n"
        "- Be concise and structured.\n"
        "- End with a 'Sources:' section listing filenames used.",
    ),
    (
        "human",
        "Context from TDR documents:\n\n{context}\n\n"
        "---\n\n"
        "User question: {question}\n\n"
        "Answer using only the context above.",
    ),
])


def build_generation_chain(temperature: float = DEFAULT_TEMPERATURE):
    """Build the generation chain with a specific sampling temperature.

    Reuses a per-temperature cached ChatOllama (see _get_llm) so the chain
    stays cheap to construct while still honoring a caller-supplied
    temperature.
    """
    return GENERATION_PROMPT | _get_llm(temperature) | StrOutputParser()


# Default chain kept for any code that imports `generation_chain` directly.
generation_chain = build_generation_chain(DEFAULT_TEMPERATURE)


# ── Graph nodes ──────────────────────────────────────────────────

def expand_queries_node(state: RAGState) -> RAGState:
    query = state["query"]
    print(f"\n🔍 Expanding query: '{query}'")
    expanded = expand_query(query)
    print(f"   Expanded: {expanded}")
    return {"expanded_queries": expanded}


def retrieve_node(state: RAGState) -> RAGState:
    limit = state.get("context_limit", 5)
    print(f"\n📚 Retrieving top {limit} chunks...")
    # Reuse the expansions already produced by expand_queries_node so we
    # don't trigger a second query-expansion LLM call inside the retriever.
    chunks = retrieve_context(
        state["query"],
        limit=limit,
        expanded_queries=state.get("expanded_queries"),
    )

    sources = [
        {
            "filename": c.get("filename", "Unknown"),
            "chunk_index": c.get("chunk_index", 0),
            "score": c.get("score", 0.0),
        }
        for c in chunks
    ]
    return {"context_chunks": chunks, "sources": sources}


def format_context(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        parts.append(
            f"[Source {i}] File: {chunk.get('filename', 'Unknown')} "
            f"| Score: {chunk.get('score', 0.0):.4f}\n"
            f"{chunk.get('content', '').strip()}"
        )
    return "\n\n".join(parts)


def generate_node(state: RAGState) -> RAGState:
    chunks = state.get("context_chunks", [])

    if not chunks:
        return {
            "answer": (
                "I could not find relevant information in the TDR document "
                "database to answer your question."
            )
        }

    print("\n✍️ Generating answer with LangChain + Ollama...")
    context = format_context(chunks)

    # Use the temperature passed into run_rag_graph() (defaults to
    # DEFAULT_TEMPERATURE if not provided), instead of the old hardcoded
    # module-level chain that ignored this value entirely.
    temperature = state.get("temperature", DEFAULT_TEMPERATURE)
    chain = build_generation_chain(temperature)

    answer = chain.invoke({
        "context": context,
        "question": state["query"],
    })

    return {"answer": answer}


# ── Build & compile graph ────────────────────────────────────────

def build_rag_graph():
    graph = StateGraph(RAGState)

    graph.add_node("expand", expand_queries_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)

    graph.add_edge(START, "expand")
    graph.add_edge("expand", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", END)

    return graph.compile()


rag_app = build_rag_graph()


def run_rag_graph(
    user_query: str,
    context_limit: int = 5,
    temperature: float = DEFAULT_TEMPERATURE,
) -> dict:
    """Run the full LangGraph RAG pipeline."""
    result = rag_app.invoke({
        "query": user_query,
        "context_limit": context_limit,
        "temperature": temperature,
    })

    return {
        "query": user_query,
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "expanded_queries": result.get("expanded_queries", []),
        "context_chunks": result.get("context_chunks", []),
    }