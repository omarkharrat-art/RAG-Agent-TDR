"""Filter/metadata route.

Exposes what's available in the indexed corpus so a UI can build filters —
e.g. the list of source documents and how many chunks each contributed.
Reads directly from the Qdrant collection by scrolling stored payloads.
"""

from fastapi import APIRouter, HTTPException

from backend.core import config, qdrant_client

router = APIRouter(prefix="/filters", tags=["filters"])


@router.get("/documents")
def list_documents() -> dict:
    """List the source documents present in the collection, with chunk counts."""
    if not qdrant_client.check_qdrant_health():
        raise HTTPException(status_code=503, detail="Qdrant is unavailable.")

    client = qdrant_client.get_qdrant_client()

    counts: dict[str, int] = {}
    next_page = None
    try:
        # Scroll through every point's payload, tallying filenames. Only the
        # filename payload is fetched (with_vectors=False) to keep it light.
        while True:
            points, next_page = client.scroll(
                collection_name=config.COLLECTION_NAME,
                limit=256,
                offset=next_page,
                with_payload=["filename"],
                with_vectors=False,
            )
            for p in points:
                filename = (p.payload or {}).get("filename", "Unknown")
                counts[filename] = counts.get(filename, 0) + 1
            if next_page is None:
                break
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read collection: {e}")

    documents = [
        {"filename": name, "chunks": n}
        for name, n in sorted(counts.items(), key=lambda kv: kv[0].lower())
    ]

    return {
        "status": "success",
        "collection": config.COLLECTION_NAME,
        "document_count": len(documents),
        "total_chunks": sum(counts.values()),
        "documents": documents,
    }
