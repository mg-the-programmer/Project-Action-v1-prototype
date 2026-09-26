"""Upsert enriched chunks into the personal knowledge-base entries table."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Protocol

from scripts.transcribe import REPOSITORY_ROOT, load_environment_file
from shared.clients import create_supabase_client

UPSERT_KEY = "source_file,chunk_index,chunk_strategy"
REQUIRED_FIELDS = ("content", "source_type", "source_file", "chunk_index", "chunk_strategy")
STORED_FIELDS = {
    "content", "embedding", "source_type", "source_file", "audio_offset", "word_timestamps",
    "chunk_index", "chunk_strategy", "tags", "mood", "topic_label", "moment_type", "visual_context",
}


class EntriesTable(Protocol):
    def upsert(self, rows: list[dict[str, Any]], *, on_conflict: str) -> Any: ...


def entry_rows(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate chunks and select precisely the database-owned entry fields."""
    rows: list[dict[str, Any]] = []
    for index, chunk in enumerate(chunks):
        missing = [field for field in REQUIRED_FIELDS if chunk.get(field) is None]
        if missing:
            raise ValueError(f"Chunk {index} is missing required fields: {', '.join(missing)}")
        rows.append({field: chunk[field] for field in STORED_FIELDS if field in chunk})
    return rows


def store_chunks(chunks: list[dict[str, Any]], client: Any | None = None) -> int:
    """Upsert chunks by their stable source/chunk/strategy identity."""
    rows = entry_rows(chunks)
    if not rows:
        return 0
    database = client or create_supabase_client()
    response = database.table("entries").upsert(rows, on_conflict=UPSERT_KEY).execute()
    return len(response.data or rows)


def store_file(path: Path, client: Any | None = None) -> tuple[Path, int]:
    chunks = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(chunks, list):
        raise ValueError(f"Chunk file must contain an array: {path}")
    return path, store_chunks(chunks, client)


def main() -> int:
    parser = argparse.ArgumentParser(description="Upsert an enriched chunk JSON file into Supabase.")
    parser.add_argument("chunks", type=Path)
    args = parser.parse_args()
    load_environment_file(REPOSITORY_ROOT / ".env")
    try:
        path, count = store_file(args.chunks)
        print(f"Upserted {count} entries from {path}")
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"Error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
