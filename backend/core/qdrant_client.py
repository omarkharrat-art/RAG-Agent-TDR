from qdrant_client import QdrantClient, models
from backend.core import config

_client = None

def get_qdrant_client() -> QdrantClient:
    """Returns a singleton QdrantClient instance."""
    global _client
    if _client is None:
        _client = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)
    return _client

def check_qdrant_health() -> bool:
    """Checks if Qdrant service is running and reachable."""
    try:
        client = get_qdrant_client()
        # Ping check by getting collections list
        client.get_collections()
        return True
    except Exception as e:
        print(f"❌ Qdrant Health Check Failed: {e}")
        return False

def search_similar_points(
    query_vector: list[float],
    limit: int = 5,
    filename: str | None = None,
) -> list:
    """Searches Qdrant for similar points using the given query vector.

    Args:
        query_vector: List of floats representing the query embedding.
        limit: Max number of search results to return.
        filename: Optional exact filename to restrict the search to a single
            document (payload filter). When set, only chunks from that file are
            considered — used to scope a query to one specific TdR.

    Returns:
        List of returned points.
    """
    try:
        client = get_qdrant_client()

        query_filter = None
        if filename:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="filename",
                        match=models.MatchValue(value=filename),
                    )
                ]
            )

        response = client.query_points(
            collection_name=config.COLLECTION_NAME,
            query=query_vector,
            limit=limit,
            query_filter=query_filter,
        )
        return response.points
    except Exception as e:
        print(f"❌ Qdrant Search Failed: {e}")
        return []


def list_document_filenames() -> list[str]:
    """Return the distinct source filenames present in the collection.

    Scrolls every point's payload (filename only, no vectors) and collects the
    unique filenames — used to count / list the indexed TdR documents.
    """
    try:
        client = get_qdrant_client()
        names: set[str] = set()
        next_page = None
        while True:
            points, next_page = client.scroll(
                collection_name=config.COLLECTION_NAME,
                limit=256,
                offset=next_page,
                with_payload=["filename"],
                with_vectors=False,
            )
            for p in points:
                fn = (p.payload or {}).get("filename")
                if fn:
                    names.add(fn)
            if next_page is None:
                break
        return sorted(names)
    except Exception as e:
        print(f"❌ Qdrant document listing failed: {e}")
        return []
