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
from shared.feedback import log_retrieval, rate_retrieval
from shared.retrieval import search_entries as retrieve_entries

CONTEXT_FIELDS = (
    "id,content,source_type,source_file,audio_offset,chunk_index,chunk_strategy,"
    "tags,mood,topic_label,moment_type,visual_context,recorded_at"
)
ALLOWED_SOURCE_TYPES = {"voice_memo", "notion_note"}


class EntriesClient(Protocol):
    """The Supabase operations needed by the non-retrieval MCP tools."""

    def table(self, table_name: str) -> Any: ...


def add_trigger_word(
    word: str, *, client: EntriesClient | None = None
) -> dict[str, Any]:
    """Add a unique exact-match boost term and report the current list size."""
    _require_text("word", word)
    normalized_word = word.strip()
    database = client or create_supabase_client()
    existing = (
        database.table("trigger_words")
        .select("word")
        .eq("word", normalized_word)
        .execute()
        .data
        or []
    )
    if existing:
        return {
            "word": normalized_word,
            "already_exists": True,
            "count": _trigger_word_count(database),
        }

    inserted = (
        database.table("trigger_words")
        .upsert(
            {"word": normalized_word},
            on_conflict="word",
            ignore_duplicates=True,
        )
        .execute()
        .data
        or []
    )
    return {
        "word": normalized_word,
        "already_exists": not bool(inserted),
        "count": _trigger_word_count(database),
    }


def list_trigger_words(*, client: EntriesClient | None = None) -> list[dict[str, Any]]:
    """Return the full trigger vocabulary, newest term first."""
    database = client or create_supabase_client()
    return (
        database.table("trigger_words")
        .select("word,added_at")
        .order("added_at", desc=True)
        .execute()
        .data
        or []
    )


def _trigger_word_count(database: EntriesClient) -> int:
    """Count trigger terms after a successful add or duplicate lookup."""
    return len(database.table("trigger_words").select("word").execute().data or [])


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


def list_entries(
    *,
    tag: str | None = None,
    start: str | None = None,
    end: str | None = None,
    source_type: str | None = None,
    client: EntriesClient | None = None,
) -> list[dict[str, Any]]:
    """Return entries matching the supplied dashboard and MCP filters."""
    if tag is not None:
        _require_text("tag", tag)
    if start is not None and end is not None:
        _validate_date_range(start, end)
    elif start is not None:
        _require_text("start", start)
        _parse_datetime(start)
    elif end is not None:
        _require_text("end", end)
        _parse_datetime(end)
    if source_type is not None and source_type not in ALLOWED_SOURCE_TYPES:
        raise ValueError("source_type must be voice_memo or notion_note")
    database = client or create_supabase_client()
    query = database.table("entries").select(CONTEXT_FIELDS)
    if tag is not None:
        query = query.contains("tags", [tag.strip()])
    if start is not None:
        query = query.gte("recorded_at", start)
    if end is not None:
        query = query.lte("recorded_at", end)
    if source_type is not None:
        query = query.eq("source_type", source_type)
    return query.order("recorded_at", desc=True).execute().data or []


def list_by_tag(tag: str, *, client: EntriesClient | None = None) -> list[dict[str, Any]]:
    """Return entries carrying ``tag``, most recently recorded first."""
    return list_entries(tag=tag, client=client)


def list_by_date_range(
    start: str, end: str, *, client: EntriesClient | None = None
) -> list[dict[str, Any]]:
    """Return entries recorded inclusively between two ISO-8601 timestamps."""
    return list_entries(start=start, end=end, client=client)


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
def search_entries(query: str, top_k: int = 15, weight: float = 0.7) -> dict[str, Any]:
    """Search entries, log the interaction, and return results with its log id."""
    database = create_supabase_client()
    results = retrieve_entries(query, top_k=top_k, weight=weight, client=database)
    return {"log_id": log_retrieval(query, results, client=database), "results": results}


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


@server.tool(name="log_feedback")
def log_feedback_tool(query: str, results: list[dict[str, Any]], rating: int, comment: str) -> dict[str, str]:
    """Record a rated retrieval interaction that happened outside search_entries."""
    return {"log_id": log_retrieval(query, results, rating=rating, comment=comment)}


@server.tool(name="rate_retrieval")
def rate_retrieval_tool(log_id: str, rating: int, comment: str) -> dict[str, str]:
    """Attach a one-to-five usefulness rating and comment to a retrieval log."""
    return {"log_id": rate_retrieval(log_id, rating, comment)}


@server.tool(name="add_trigger_word")
def add_trigger_word_tool(word: str) -> dict[str, Any]:
    """Add a trigger word or phrase for exact-match retrieval boosting."""
    return add_trigger_word(word)


@server.tool(name="list_trigger_words")
def list_trigger_words_tool() -> list[dict[str, Any]]:
    """List trigger words and their added timestamps, newest first."""
    return list_trigger_words()


def main() -> None:
    """Load local configuration and serve MCP messages on standard input/output."""
    load_environment_file(REPOSITORY_ROOT / ".env")
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
