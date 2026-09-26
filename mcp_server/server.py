"""Stdio MCP tools for querying and adding personal knowledge-base entries."""
from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from mcp.server.fastmcp import FastMCP

from scripts.store import store_chunks
from scripts.tag import openai_tag
from scripts.transcribe import load_environment_file
from shared.clients import create_supabase_client, embed_texts
from shared.retrieval import search_entries as retrieve_entries

CONTEXT_FIELDS = (
    "id,content,source_type,source_file,audio_offset,chunk_index,chunk_strategy,"
    "tags,mood,topic_label,moment_type,visual_context,recorded_at"
)
ALLOWED_SOURCE_TYPES = {"voice_memo", "notion_note"}


class EntriesClient(Protocol):
    """The Supabase operations needed by the non-retrieval MCP tools."""

    def table(self, table_name: str) -> Any: ...


def get_entry_context(entry_id: str, *, client: EntriesClient | None = None) -> list[dict[str, Any]]:
    """Return the target chunk and its immediate neighbours from the same source."""
    _require_text("id", entry_id)
    database = client or create_supabase_client()
    found = database.table("entries").select(
        "source_file,chunk_index,chunk_strategy"
    ).eq("id", entry_id).execute().data or []
    if not found:
        raise ValueError("No entry exists for the supplied id")
    entry = found[0]
    source_file = entry.get("source_file")
    chunk_index = entry.get("chunk_index")
    if not isinstance(source_file, str) or not isinstance(chunk_index, int):
        raise ValueError("The entry does not have source chunk metadata")

    query = (
        database.table("entries")
        .select(CONTEXT_FIELDS)
        .eq("source_file", source_file)
        .gte("chunk_index", max(0, chunk_index - 1))
        .lte("chunk_index", chunk_index + 1)
        .order("chunk_index")
    )
    return query.execute().data or []


def list_by_tag(tag: str, *, client: EntriesClient | None = None) -> list[dict[str, Any]]:
    """Return entries carrying ``tag``, most recently recorded first."""
    _require_text("tag", tag)
    database = client or create_supabase_client()
    return (
        database.table("entries")
        .select(CONTEXT_FIELDS)
        .contains("tags", [tag.strip()])
        .order("recorded_at", desc=True)
        .execute()
        .data
        or []
    )


def list_by_date_range(
    start: str, end: str, *, client: EntriesClient | None = None
) -> list[dict[str, Any]]:
    """Return entries recorded inclusively between two ISO-8601 timestamps."""
    _validate_date_range(start, end)
    database = client or create_supabase_client()
    return (
        database.table("entries")
        .select(CONTEXT_FIELDS)
        .gte("recorded_at", start)
        .lte("recorded_at", end)
        .order("recorded_at", desc=True)
        .execute()
        .data
        or []
    )


def ingest_entry(
    text: str,
    source_type: str,
    recorded_at: str | None = None,
    *,
    client: Any | None = None,
    embedder: Callable[[list[str]], list[list[float]]] = embed_texts,
    tagger: Callable[[str], Awaitable[dict[str, Any]]] = openai_tag,
) -> dict[str, Any]:
    """Embed, tag, and store one text entry submitted through Claude Desktop."""
    return asyncio.run(
        _ingest_entry(text, source_type, recorded_at, client=client, embedder=embedder, tagger=tagger)
    )


async def _ingest_entry(
    text: str,
    source_type: str,
    recorded_at: str | None = None,
    *,
    client: Any | None = None,
    embedder: Callable[[list[str]], list[list[float]]] = embed_texts,
    tagger: Callable[[str], Awaitable[dict[str, Any]]] = openai_tag,
) -> dict[str, Any]:
    """Implement ingestion without starting a new event loop for MCP requests."""
    _require_text("text", text)
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise ValueError("source_type must be voice_memo or notion_note")
    stored_at = recorded_at or datetime.now(timezone.utc).isoformat()
    _parse_datetime(stored_at)

    content = text.strip()
    chunk: dict[str, Any] = {
        "content": content,
        "embedding": _single_embedding(embedder, content),
        "source_type": source_type,
        "source_file": f"claude-desktop-{uuid4()}.md",
        "chunk_index": 0,
        "chunk_strategy": "pause" if source_type == "voice_memo" else "heading",
        "recorded_at": stored_at,
    }
    metadata = await tagger(content)
    chunk.update({key: metadata.get(key) for key in ("tags", "mood", "topic_label", "moment_type", "visual_context")})
    database = client or create_supabase_client()
    store_chunks([chunk], client=database)
    return chunk


def _single_embedding(embedder: Callable[[list[str]], list[list[float]]], text: str) -> list[float]:
    embeddings = embedder([text])
    if len(embeddings) != 1:
        raise ValueError("Embedding provider returned an unexpected number of vectors")
    return embeddings[0]


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must contain non-whitespace text")


def _validate_date_range(start: str, end: str) -> None:
    _require_text("start", start)
    _require_text("end", end)
    if _parse_datetime(start) > _parse_datetime(end):
        raise ValueError("start must be earlier than or equal to end")


def _parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("dates must use ISO-8601 format") from error


server = FastMCP("Personal Knowledge Base")


@server.tool(name="search_entries")
def search_entries(query: str, top_k: int = 15, weight: float = 0.7) -> list[dict[str, Any]]:
    """Search entries with blended semantic and exact-match retrieval."""
    return retrieve_entries(query, top_k=top_k, weight=weight)


@server.tool(name="get_entry_context")
def get_entry_context_tool(id: str) -> list[dict[str, Any]]:
    """Read an entry with immediately adjacent chunks from its source file."""
    return get_entry_context(id)


@server.tool(name="list_by_tag")
def list_by_tag_tool(tag: str) -> list[dict[str, Any]]:
    """List all entries with a tag, newest first."""
    return list_by_tag(tag)


@server.tool(name="list_by_date_range")
def list_by_date_range_tool(start: str, end: str) -> list[dict[str, Any]]:
    """List entries recorded in an inclusive ISO-8601 date range, newest first."""
    return list_by_date_range(start, end)


@server.tool(name="ingest_entry")
async def ingest_entry_tool(text: str, source_type: str, recorded_at: str | None = None) -> dict[str, Any]:
    """Add one journal or note entry through embedding, tagging, and storage."""
    return await _ingest_entry(text, source_type, recorded_at)


def main() -> None:
    """Load local configuration and serve MCP messages on standard input/output."""
    load_environment_file(REPOSITORY_ROOT / ".env")
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
