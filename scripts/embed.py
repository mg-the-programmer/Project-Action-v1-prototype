"""Add 1536-dimensional OpenAI embeddings to chunk JSON files."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from shared.clients import embed_texts

BATCH_SIZE = 100


def enrich_chunks(chunks: list[dict[str, Any]], embedder: Callable[[list[str]], list[list[float]]] = embed_texts) -> int:
    pending = [chunk for chunk in chunks if not _has_valid_embedding(chunk)]
    for offset in range(0, len(pending), BATCH_SIZE):
        batch = pending[offset : offset + BATCH_SIZE]
        vectors = embedder([str(chunk["content"]) for chunk in batch])
        if len(vectors) != len(batch):
            raise ValueError("Embedding provider returned an unexpected number of vectors")
        for chunk, vector in zip(batch, vectors):
            if len(vector) != 1536:
                raise ValueError(f"Expected 1536 embedding dimensions, got {len(vector)}")
            chunk["embedding"] = vector
    return len(pending)


def _has_valid_embedding(chunk: dict[str, Any]) -> bool:
    embedding = chunk.get("embedding")
    return isinstance(embedding, list) and len(embedding) == 1536


def embed_file(path: Path, embedder: Callable[[list[str]], list[list[float]]] = embed_texts) -> tuple[Path, int]:
    chunks = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(chunks, list):
        raise ValueError(f"Chunk file must contain an array: {path}")
    count = enrich_chunks(chunks, embedder)
    path.write_text(json.dumps(chunks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path, count


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate embeddings for a chunk JSON file.")
    parser.add_argument("chunks", type=Path)
    args = parser.parse_args()
    path, count = embed_file(args.chunks)
    print(f"Embedded {count} chunks in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
