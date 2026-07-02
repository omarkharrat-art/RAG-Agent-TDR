#!/usr/bin/env python3
"""Precompute embeddings for document chunks and upsert them to Qdrant.

This script loads chunk files from `data/chunks` and/or `data/extracted` and
computes embeddings using `sentence-transformers` on CPU, then upserts vectors
and payloads into the configured Qdrant collection.

It is idempotent: repeated runs will overwrite existing points with the same
`chunk_id`.
"""
import os
import json
from pathlib import Path
from typing import Iterable

from sentence_transformers import SentenceTransformer

from backend.core import config
from backend.core.qdrant_client import get_qdrant_client


def find_chunk_files(root: Path) -> Iterable[Path]:
    for sub in (root / "chunks", root / "extracted"):
        if sub.exists() and sub.is_dir():
            for p in sub.glob("*.json"):
                yield p


def load_chunks_from_file(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    # Accept either a list of chunks or a dict with a 'chunks' key
    if isinstance(data, dict) and "chunks" in data:
        items = data["chunks"]
    elif isinstance(data, list):
        items = data
    else:
        # Fallback: wrap the dict as a single item
        items = [data]
    return items


def prepare_points(chunks: list[dict]) -> list[tuple[str, list[float], dict]]:
    points = []
    for c in chunks:
        chunk_id = str(c.get("chunk_id") or c.get("id") or c.get("chunkId") or "")
        if not chunk_id:
            # Skip unnamed chunks
            continue
        content = c.get("content") or c.get("text") or ""
        filename = c.get("filename") or c.get("source") or "unknown"
        answer = c.get("answer")
        payload = {
            "chunk_id": chunk_id,
            "filename": filename,
            "chunk_index": c.get("chunk_index", 0),
            "content": content,
            "answer": answer,
        }
        points.append((chunk_id, content, payload))
    return points


def batch_upsert(client, model, points, batch_size=64):
    from qdrant_client.http import models as rest

    batches = [points[i : i + batch_size] for i in range(0, len(points), batch_size)]
    count = 0
    for batch in batches:
        ids = [p[0] for p in batch]
        texts = [p[1] for p in batch]
        payloads = [p[2] for p in batch]

        vectors = model.encode(texts, show_progress_bar=False)
        # qdrant upsert expects list of PointStruct or dicts
        points_for_upsert = []
        for _id, vec, payload in zip(ids, vectors, payloads):
            points_for_upsert.append(rest.PointStruct(id=_id, vector=vec.tolist() if hasattr(vec, 'tolist') else vec, payload=payload))

        client.upsert(collection_name=config.COLLECTION_NAME, points=points_for_upsert)
        count += len(points_for_upsert)
        print(f"Upserted {count} vectors so far...")


def main():
    repo_root = Path(os.getcwd())
    data_root = repo_root / "data"

    files = list(find_chunk_files(repo_root))
    if not files:
        print("No chunk files found under data/chunks or data/extracted. Exiting.")
        return

    print(f"Found {len(files)} files to process")

    all_chunks = []
    for f in files:
        try:
            chunks = load_chunks_from_file(f)
            all_chunks.extend(chunks)
            print(f"Loaded {len(chunks)} chunks from {f}")
        except Exception as e:
            print(f"Failed to load {f}: {e}")

    if not all_chunks:
        print("No chunks to index. Exiting.")
        return

    print(f"Preparing {len(all_chunks)} points for embedding")
    points = prepare_points(all_chunks)

    print("Loading SentenceTransformer model on CPU...")
    model = SentenceTransformer(config.EMBEDDING_MODEL, device='cpu')

    client = get_qdrant_client()
    # Ensure collection exists (best-effort). If not, create with vector size from config
    try:
        client.get_collection(collection_name=config.COLLECTION_NAME)
    except Exception:
        print(f"Collection {config.COLLECTION_NAME} not found; attempting to create it.")
        try:
            client.recreate_collection(collection_name=config.COLLECTION_NAME, vector_size=config.VECTOR_SIZE, distance="Cosine")
        except Exception as e:
            print(f"Failed to create collection: {e}")

    print("Upserting vectors to Qdrant...")
    batch_upsert(client, model, points, batch_size=32)

    print("Done.")


if __name__ == "__main__":
    main()
