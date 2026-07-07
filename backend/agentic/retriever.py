import sys
import hashlib
from backend.core import config, qdrant_client
from backend.agentic.query_expander import expand_query

# Fix Unicode output on Windows terminals
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import logging

logger = logging.getLogger(__name__)

# Singleton loader for embedding model (may be real or fallback)
_model = None

# True once we've fallen back to hash-based (non-semantic) embeddings.
# Exposed via is_using_fallback() so callers / health checks can surface it.
_using_fallback = False


def is_using_fallback() -> bool:
    """Whether the retriever is running on non-semantic fallback embeddings.

    Fallback vectors are deterministic hashes with the right dimensionality
    but no semantic meaning, and they do NOT match the real vectors stored at
    index time — so retrieval quality is effectively random. This should
    never be True in a real deployment.
    """
    # Ensure the model has been resolved at least once.
    if _model is None:
        get_embedding_model()
    return _using_fallback


class FallbackModel:
    """Simple deterministic fallback embedding generator.

    Produces a fixed-length vector from text by hashing; not semantic,
    but allows the service to run when heavy ML deps are not installed.
    """
    def __init__(self, vector_size: int):
        self.vector_size = vector_size

    def encode(self, text: str):
        # Create a deterministic byte stream and map to floats in [-1,1]
        digest = hashlib.sha256(text.encode('utf-8')).digest()
        out = []
        cur = digest
        while len(out) < self.vector_size:
            for b in cur:
                out.append((b / 255.0) * 2.0 - 1.0)
                if len(out) >= self.vector_size:
                    break
            cur = hashlib.sha256(cur).digest()
        return out[: self.vector_size]


def get_embedding_model():
    """Return a model with an `encode(text)` method.

    Tries to lazily import `sentence_transformers` + `torch`. If unavailable,
    returns `FallbackModel`.
    """
    global _model, _using_fallback
    if _model is not None:
        return _model

    try:
        # Lazy import heavy ML libs only when available
        import torch as _torch  # type: ignore
        from sentence_transformers import SentenceTransformer as _ST  # type: ignore

        device = 'cuda' if _torch.cuda.is_available() else 'cpu'
        print(f"🖥️ Loading SentenceTransformer on device: {device}...")
        _model = _ST(config.EMBEDDING_MODEL, device=device)
        _using_fallback = False
        print("✅ Embedding model loaded successfully")
    except Exception as e:
        _using_fallback = True
        # Loud, structured warning: fallback embeddings silently destroy
        # retrieval quality, so this must never pass unnoticed.
        logger.error(
            "sentence-transformers/torch unavailable (%s). Falling back to "
            "NON-SEMANTIC hash embeddings — retrieval results will be "
            "meaningless. Install the ML dependencies for real search.",
            e,
        )
        print(
            "🚨 WARNING: using NON-SEMANTIC fallback embeddings — "
            f"retrieval quality is effectively random. Reason: {e}"
        )
        _model = FallbackModel(config.VECTOR_SIZE)

    return _model


def _to_vector_list(raw) -> list[float]:
    """Normalize an embedding output (numpy array, torch tensor, or plain
    list) into a plain Python list of floats.

    SentenceTransformer.encode() returns a numpy array (which has
    .tolist()), but FallbackModel.encode() returns a plain list already.
    Calling .tolist() unconditionally breaks on the fallback path with:
        AttributeError: 'list' object has no attribute 'tolist'
    """
    if hasattr(raw, "tolist"):
        return raw.tolist()
    return list(raw)


# ── Cross-encoder reranker ───────────────────────────────────────────
# Embedding search is fast but only finds "same-topic" chunks. A cross-encoder
# reads (query, chunk) TOGETHER and scores true relevance, so the chunk that
# actually answers the question rises to the top. We load it lazily and fail
# safe: if it can't load, retrieval falls back to embedding order.

_reranker = None
_reranker_failed = False


def _get_reranker():
    """Lazily load the cross-encoder reranker, or None if unavailable."""
    global _reranker, _reranker_failed
    if _reranker is not None or _reranker_failed:
        return _reranker

    try:
        import torch as _torch  # type: ignore
        from sentence_transformers import CrossEncoder  # type: ignore

        device = "cuda" if _torch.cuda.is_available() else "cpu"
        print(f"🔁 Loading reranker {config.RERANK_MODEL} on {device}...")
        _reranker = CrossEncoder(config.RERANK_MODEL, device=device)
        print("✅ Reranker loaded")
    except Exception as e:
        _reranker_failed = True
        logger.warning(
            "Reranker unavailable (%s). Falling back to embedding-only order.", e
        )
        print(f"⚠️ Reranker unavailable ({e}); using embedding order.")
    return _reranker


def _rerank(query: str, candidates: list[dict], limit: int) -> list[dict]:
    """Re-score candidate chunks by (query, chunk) relevance, best first.

    Returns the top `limit`. If the reranker is disabled or fails to load, the
    candidates are returned unchanged (already sorted by embedding score).
    """
    if not config.RERANK_ENABLED or len(candidates) <= 1:
        return candidates[:limit]

    reranker = _get_reranker()
    if reranker is None:
        return candidates[:limit]

    try:
        pairs = [[query, c.get("content", "")] for c in candidates]
        scores = reranker.predict(pairs)
        for c, s in zip(candidates, scores):
            c["rerank_score"] = float(s)
        candidates.sort(key=lambda c: c["rerank_score"], reverse=True)
        print(f"🔁 Reranked {len(candidates)} candidates → top {limit}")
    except Exception as e:
        # Never let a reranker error break retrieval; keep embedding order.
        print(f"⚠️ Rerank failed ({e}); keeping embedding order.")
    return candidates[:limit]


def retrieve_context(
    user_query: str,
    limit: int = 5,
    expanded_queries: list[str] | None = None,
    filename: str | None = None,
) -> list[dict]:
    """Retrieves relevant text chunks from Qdrant using expanded queries.

    Process:
    1. Expands the original query into multiple search variations
    2. Generates embeddings for each variation
    3. Queries Qdrant for similar points
    4. Deduplicates results by chunk_id
    5. Returns top-ranked unique chunks

    Args:
        user_query: Original raw user search string.
        limit: Max number of context chunks to return (default: 5).
        expanded_queries: Optional pre-expanded query variations. When the
            caller (e.g. the LangGraph pipeline) has already run query
            expansion, pass the result here to avoid a second, redundant
            LLM call. If None, expansion is performed internally.

    Returns:
        List of dictionaries with keys: chunk_id, filename, chunk_index, content, score.
        Returns empty list if no results found or query is invalid.
    """
    if not user_query or not user_query.strip():
        print("⚠️ Empty query provided to retrieve_context")
        return []

    # 1. Use caller-supplied expansions if available, otherwise expand here.
    if expanded_queries is None:
        expanded_queries = expand_query(user_query)
    if not expanded_queries:
        print("⚠️ Query expansion returned empty list")
        return []
    
    print(f"🔍 Expanded queries: {expanded_queries}")
    
    # 2. Get the embedding model
    try:
        model = get_embedding_model()
    except Exception as e:
        print(f"❌ Failed to load embedding model: {e}")
        return []
    
    # 3. Retrieve chunks for all query variations
    all_results = []
    for q in expanded_queries:
        try:
            # Generate embedding for this query
            query_vector = _to_vector_list(model.encode(q))
            
            # Search Qdrant. When reranking, cast a WIDER net (RERANK_CANDIDATES)
            # so the truly-relevant chunk is in the pool for the cross-encoder to
            # surface; otherwise fetch a smaller multiple of the final limit.
            # `filename`, when set, restricts retrieval to a single document.
            fetch_limit = config.RERANK_CANDIDATES if config.RERANK_ENABLED else limit * 3
            points = qdrant_client.search_similar_points(
                query_vector, limit=fetch_limit, filename=filename
            )
            
            if points:
                print(f"   Found {len(points)} results for: '{q}'")
                all_results.extend(points)
            else:
                print(f"   No results found for: '{q}'")
                
        except Exception as e:
            print(f"❌ Retriever error during search for '{q}': {e}")
            continue  # Continue with next query instead of failing completely
    
    if not all_results:
        print(f"⚠️ No relevant context found for query: '{user_query}'")
        return []
    
    # 4. Deduplicate by PARENT (hierarchical / small-to-big retrieval).
    #    We matched on small child chunks, but several children can belong to
    #    the same parent section — collapse them into one result and return the
    #    parent_content so the LLM sees the full block (e.g. a whole table).
    #    Falls back to chunk_id / content for older, non-hierarchical indexes.
    seen = {}

    for point in all_results:
        payload = point.payload or {}
        chunk_id = payload.get("chunk_id")

        # Skip points without chunk_id
        if not chunk_id:
            print(f"⚠️ Skipping point without chunk_id: {payload}")
            continue

        # Key by parent when present so sibling children merge into one result.
        dedup_key = payload.get("parent_id") or chunk_id
        # Prefer the large parent block; fall back to child content if absent.
        content = payload.get("parent_content") or payload.get("content", "")

        # Keep the highest scoring child for each parent.
        if dedup_key not in seen or point.score > seen[dedup_key]["score"]:
            seen[dedup_key] = {
                "chunk_id": chunk_id,
                "parent_id": payload.get("parent_id"),
                "filename": payload.get("filename", "Unknown"),
                "chunk_index": payload.get("chunk_index", 0),
                "content": content,
                "answer": payload.get("answer"),
                "score": point.score,
            }

    unique_results = list(seen.values())

    # 5. Sort deduplicated results by embedding score (the reranker will refine
    #    this, but ordering first keeps behavior sane if reranking is disabled).
    unique_results.sort(key=lambda x: x["score"], reverse=True)

    print(f"✅ Retrieved {len(unique_results)} unique chunks after deduplication")

    # 6. Rerank against the ORIGINAL user query (not the expansions) and return
    #    the top `limit`. Reranking on the real question is what fixes the
    #    "right document, wrong chunk" problem embedding-only search has.
    return _rerank(user_query, unique_results, limit)