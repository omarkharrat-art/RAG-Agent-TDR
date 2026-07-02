from qdrant_client import QdrantClient
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

def search_similar_points(query_vector: list[float], limit: int = 5) -> list:
    """Searches Qdrant for similar points using the given query vector.
    
    Args:
        query_vector: List of floats representing the query embedding.
        limit: Max number of search results to return.
        
    Returns:
        List of returned points.
    """
    try:
        client = get_qdrant_client()
        response = client.query_points(
            collection_name=config.COLLECTION_NAME,
            query=query_vector,
            limit=limit
        )
        return response.points
    except Exception as e:
        print(f"❌ Qdrant Search Failed: {e}")
        return []
