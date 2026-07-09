import re
import sys
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_ollama import ChatOllama

from backend.core import config, qdrant_client
from backend.agentic.query_expander import expand_query
from backend.agentic.retriever import retrieve_context
from backend.agentic.reflector import reflect_on_context

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
    filename: str  # optional: restrict retrieval to one document
    route: str  # "count" (metadata tool) or "rag" (normal pipeline)
    # Reflect-and-retry loop state:
    retries: int  # how many retry cycles have run so far
    max_retries: int  # cap so the cycle can never loop forever
    reflection: dict  # {"sufficient": bool, "reason": str} from the reflect node


DEFAULT_TEMPERATURE = 0.2

# ── LangChain LLM + prompt ───────────────────────────────────────

# The chat model comes from the provider-aware factory (Ollama or Groq),
# selected by config.LLM_PROVIDER. See backend/core/llm.py.
def _get_llm(temperature: float):
    from backend.core.llm import get_chat_llm

    return get_chat_llm(temperature)


GENERATION_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are an expert assistant for Terms of Reference (TDR / TdR) documents "
        "used in international development and consultancy missions.\n\n"
        "GROUNDING (most important):\n"
        "- Use ONLY facts stated in the provided context. Never use outside knowledge.\n"
        "- If the context does not contain the answer, reply with exactly one sentence "
        "saying the information is not available in the documents — do not guess.\n"
        "- If the context gives conflicting or per-document values (e.g. different "
        "durations across missions), present them as distinct items rather than "
        "merging them into one wrong number.\n\n"
        "STYLE:\n"
        "- Answer directly. Do NOT restate the question or add filler like "
        "'According to the provided context'.\n"
        "- Be concise: a short lead sentence, then Markdown bullet points for the "
        "key facts. Bold the important term in each bullet. Use bullets ONLY for "
        "facts that have no associated value.\n"
        "- DEFAULT TO A MARKDOWN TABLE (not bullets) whenever each item has an "
        "associated value — criteria with weights/percentages/scores, tasks with "
        "durations/deadlines, amounts, comparison grids — EVEN IF the user did not "
        "say 'tableau' or 'table'. A list of criteria each followed by a % or a "
        "score must be rendered as a two-column table, never as a bulleted list.\n"
        "- If the retrieved context already contains a Markdown table that answers "
        "the question, reproduce that table as-is (same rows, columns and values).\n"
        "- TABLE RULES: (a) reproduce every row and every column exactly; (b) keep "
        "each value on the SAME row as its own label — never shift text into the "
        "wrong column; (c) for a nested table where a category (e.g. 'Offre "
        "technique 60%') has sub-criteria that each carry their own value, put "
        "each sub-criterion on its own row with its own value; (d) include any "
        "subtotal or 'Total' row; (e) if a cell's value is not in the context, "
        "leave it empty — do not invent a number or claim the sources conflict.\n"
        "- Respond in the SAME language as the user's question (French question → "
        "French answer).\n"
        "- Do NOT list sources inside the body. A separate 'Sources' section is "
        "appended automatically, so end your answer after the last fact.",
    ),
    (
        "human",
        "Context from TDR documents:\n\n{context}\n\n"
        "---\n\n"
        "Question: {question}\n\n"
        "Answer using only the context above, following the STYLE rules.",
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
    retries = state.get("retries", 0)

    # On a retry pass, broaden the query so this attempt actually differs from
    # the last one — re-running the identical expansion would retrieve the same
    # weak chunks and make the loop pointless.
    if retries > 0:
        print(f"\n🔁 Retry #{retries}: broadening query: '{query}'")
        expand_input = f"{query} (formulation plus large, synonymes, termes généraux)"
    else:
        print(f"\n🔍 Expanding query: '{query}'")
        expand_input = query

    expanded = expand_query(expand_input)
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
        filename=state.get("filename"),
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


def reflect_node(state: RAGState) -> RAGState:
    """Judge whether the retrieved context is sufficient to answer the query.

    This is the 'agent thinking about its own work' step. Its verdict drives
    the conditional loop below (decide_after_reflect): a poor retrieval sends
    the graph back to expand for another, broader attempt.
    """
    print("\n🤔 Reflecting on retrieved context...")
    verdict = reflect_on_context(state["query"], state.get("context_chunks", []))
    print(f"   Reflection: sufficient={verdict['sufficient']} — {verdict['reason']}")
    return {"reflection": verdict}


def decide_after_reflect(state: RAGState) -> str:
    """Conditional edge: loop back to retry, or move on to generate.

    Returns the name of the next node. This is what makes the pipeline a real
    graph (a cycle) rather than a straight chain:
      - context sufficient          → generate
      - insufficient, retries left  → retry (loops back to expand)
      - insufficient, out of retries→ generate (answer with what we have)
    """
    reflection = state.get("reflection", {})
    sufficient = reflection.get("sufficient", True)
    retries = state.get("retries", 0)
    max_retries = state.get("max_retries", 1)

    if sufficient:
        print("   ✅ Context sufficient → generate")
        return "generate"
    if retries < max_retries:
        print(f"   ↩️  Context insufficient → retry ({retries + 1}/{max_retries})")
        return "retry"
    print("   ⚠️  Context still insufficient but out of retries → generate anyway")
    return "generate"


def increment_retry_node(state: RAGState) -> RAGState:
    """Bump the retry counter before looping back to expand.

    Kept as its own tiny node so the counter update happens exactly once per
    loop, on the retry edge — not inside expand (which also runs on the first,
    non-retry pass).
    """
    return {"retries": state.get("retries", 0) + 1}


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


def _looks_like_value(s: str) -> bool:
    """True for short, number-bearing strings like '30%', '10 points', '84'."""
    s = s.strip()
    return bool(s) and len(s) <= 24 and bool(re.search(r"\d", s)) and bool(
        re.search(r"%|points?|pts?|jours?|H/J|€|\$|\d", s)
    )


def _reflow_inline_tables(answer: str) -> str:
    """Put an inline Markdown table onto its own lines so it actually renders.

    Small models sometimes emit a whole table on ONE line (often inside a
    bullet): "… : | Critère | % | | --- | --- | | A | 35% | …". Markdown only
    renders tables that occupy their own lines, so inline like that it shows as
    raw pipes. This detects such a line and splits it into proper rows.
    """
    out = []
    for line in answer.split("\n"):
        if line.count("|") >= 5 and re.search(r"\|\s*-{2,}\s*\|", line):
            i = line.index("|")
            prose = line[:i].strip()
            cells = [c.strip() for c in line[i:].split("|")]
            cells = [c for c in cells if c != ""]
            dash = [j for j, c in enumerate(cells) if re.fullmatch(r"-{2,}", c)]
            if not dash:
                out.append(line)
                continue
            ncol = len(dash)
            header, body = cells[:ncol], cells[2 * ncol:]
            rows = [
                "| " + " | ".join(header) + " |",
                "| " + " | ".join(["---"] * ncol) + " |",
            ]
            for k in range(0, len(body), ncol):
                r = body[k:k + ncol]
                r += [""] * (ncol - len(r))
                rows.append("| " + " | ".join(r) + " |")
            if prose:
                out.append(prose)
            out.append("\n".join(rows))
        else:
            out.append(line)
    return "\n".join(out)


def _bullets_to_table(answer: str) -> str:
    """Deterministically turn a bulleted value-list into a Markdown table.

    A 3B model sometimes ignores the 'use a table' instruction and returns
    bullets like '- Critère X : 30%'. When every bullet in a contiguous block
    ends in a value, we rewrite the block as a two-column table so the user
    always gets a table for tabular data — regardless of the model's whim.
    Leaves the answer untouched if it already contains a table or isn't a
    clean value-list.
    """
    if not answer or "|" in answer:  # already a table or contains pipes
        return answer

    lines = answer.split("\n")
    idxs = [i for i, l in enumerate(lines) if re.match(r"^\s*[-*•]\s+", l)]
    if len(idxs) < 2 or idxs != list(range(idxs[0], idxs[-1] + 1)):
        return answer  # need a single contiguous block of >=2 bullets

    rows = []
    for i in idxs:
        text = re.sub(r"^\s*[-*•]\s+", "", lines[i]).strip()
        label = value = None
        if ":" in text or "：" in text:
            label, value = re.split(r"[:：]", text, maxsplit=1)[0].strip(), \
                re.split(r"[:：]", text, maxsplit=1)[1].strip()
        else:
            m = re.match(r"^(.*?)\s*\(([^()]+)\)\s*$", text)  # 'label (30%)'
            if m:
                label, value = m.group(1).strip(), m.group(2).strip()
        if not label or not _looks_like_value(value or ""):
            return answer  # a non-value bullet → don't convert, stay safe
        rows.append((label, value))

    col2 = "Pondération" if any("%" in v for _, v in rows) else "Valeur"
    table = [f"| Critère | {col2} |", "|---|---|"]
    table += [f"| {lbl} | {val} |" for lbl, val in rows]

    pre = "\n".join(lines[: idxs[0]]).strip()
    post = "\n".join(lines[idxs[-1] + 1:]).strip()
    return "\n\n".join(p for p in [pre, "\n".join(table), post] if p)


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

    # Reflow any inline table onto its own lines so Markdown renders it,
    # then guarantee a table for value-lists even if the model used bullets.
    answer = _reflow_inline_tables(answer)
    answer = _bullets_to_table(answer)

    return {"answer": _append_sources(answer, chunks)}


def _append_sources(answer: str, chunks: list[dict]) -> str:
    """Append a clean, de-duplicated Sources section to the answer.

    The generation prompt tells the model NOT to list sources inline, so we add
    them deterministically here. This keeps citations accurate (they reflect the
    chunks actually retrieved) and consistently formatted, instead of relying on
    the model to remember and spell filenames correctly.
    """
    answer = (answer or "").strip()

    # Preserve retrieval order (highest score first) while de-duplicating.
    seen: set[str] = set()
    filenames: list[str] = []
    for c in chunks:
        name = c.get("filename", "Unknown")
        if name not in seen:
            seen.add(name)
            filenames.append(name)

    if not filenames:
        return answer

    lines = "\n".join(f"- {name}" for name in filenames)
    return f"{answer}\n\n**Sources:**\n{lines}"


# ── Router + metadata "count documents" tool ─────────────────────
#
# Makes the graph agentic: instead of always running retrieve→generate, an
# entry router inspects the question. Counting / "how many documents" queries
# can't be answered from retrieved text (the count isn't written in any chunk),
# so they're routed to a dedicated count_documents tool that reads the corpus
# metadata directly. Everything else takes the normal RAG path.

# A counting question needs (a) a count-intent cue AND (b) a corpus noun.
# Both are matched loosely so typos and casual phrasing still route correctly:
#   "how many tdr are", "how manny tdrs", "combien de tdr", "nombre de documents",
#   "count the pdfs", "total number of files", "how many do you have".
#
# many/manny/manys → man+ny? tolerates the common "manny" misspelling.
_COUNT_INTENT = re.compile(
    r"(combien|nombre|quantit[ée]|how\s+man+y?s?|number\s+of|count\b|total\b|"
    r"how\s+much)",
    re.IGNORECASE,
)
_CORPUS_NOUN = re.compile(
    r"(tdr|tdrs|termes?\s+de\s+r[ée]f[ée]rence|documents?|fichiers?|files?|pdf|"
    r"do\s+you\s+have|avez[-\s]vous|y\s+a[-\s]t[-\s]il)",
    re.IGNORECASE,
)


def route_query(state: RAGState) -> str:
    """Entry router: 'count' for corpus-count questions, else 'rag'."""
    query = state.get("query", "")
    if _COUNT_INTENT.search(query) and _CORPUS_NOUN.search(query):
        print("🧭 Router → count_documents tool")
        return "count"
    print("🧭 Router → RAG pipeline")
    return "rag"


def count_documents_node(state: RAGState) -> RAGState:
    """Tool: answer how many TdR documents are indexed, from Qdrant metadata."""
    names = qdrant_client.list_document_filenames()
    n = len(names)
    answer = (
        f"La base contient actuellement **{n}** Termes de Référence (TdR) indexés."
        if n
        else "Aucun document n'est actuellement indexé dans la base."
    )
    return {
        "answer": answer,
        "sources": [],
        "context_chunks": [],
        "expanded_queries": [],
        "route": "count",
    }


# ── Build & compile graph ────────────────────────────────────────

def build_rag_graph():
    graph = StateGraph(RAGState)

    graph.add_node("count", count_documents_node)
    graph.add_node("expand", expand_queries_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("reflect", reflect_node)
    graph.add_node("bump_retry", increment_retry_node)
    graph.add_node("generate", generate_node)

    # Conditional entry: route to the count tool or the RAG pipeline.
    graph.add_conditional_edges(
        START, route_query, {"count": "count", "rag": "expand"}
    )
    graph.add_edge("count", END)

    graph.add_edge("expand", "retrieve")
    graph.add_edge("retrieve", "reflect")

    # THE CYCLE: after reflection, either generate or loop back through
    # bump_retry → expand for another, broader retrieval attempt. This
    # back-edge is what makes this a graph rather than a linear chain.
    graph.add_conditional_edges(
        "reflect",
        decide_after_reflect,
        {"generate": "generate", "retry": "bump_retry"},
    )
    graph.add_edge("bump_retry", "expand")
    graph.add_edge("generate", END)

    return graph.compile()


rag_app = build_rag_graph()


def run_rag_graph(
    user_query: str,
    context_limit: int = 5,
    temperature: float = DEFAULT_TEMPERATURE,
    filename: str | None = None,
) -> dict:
    """Run the full LangGraph RAG pipeline.

    If `filename` is given, retrieval is restricted to that single document.
    """
    initial: RAGState = {
        "query": user_query,
        "context_limit": context_limit,
        "temperature": temperature,
        "retries": 0,
        "max_retries": 1,  # one reflect-and-retry loop; raise for more attempts
    }
    if filename:
        initial["filename"] = filename

    # recursion_limit guards against any unexpected runaway cycle at the graph
    # level, independent of our own retry counter.
    result = rag_app.invoke(initial, {"recursion_limit": 25})

    return {
        "query": user_query,
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "expanded_queries": result.get("expanded_queries", []),
        "context_chunks": result.get("context_chunks", []),
        "route": result.get("route", "rag"),
        "retries": result.get("retries", 0),
        "reflection": result.get("reflection", {}),
    }