"""Shared, database-backed hybrid retrieval for personal knowledge-base entries."""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Any, Protocol

from shared.clients import create_supabase_client, embed_texts

RESULT_FIELDS = (
    "id",
    "content",
    "source_type",
    "source_file",
    "audio_offset",
    "tags",
    "mood",
    "topic_label",
    "moment_type",
    "visual_context",
    "recorded_at",
)
DEFAULT_TRIGGER_WORD_BONUS = 0.15


class DatabaseClient(Protocol):
    """The small subset of the Supabase client used for retrieval."""

    def rpc(self, function_name: str, parameters: dict[str, Any]) -> Any: ...

    def table(self, table_name: str) -> Any: ...


def search_entries(
    query: str,
    top_k: int = 15,
    weight: float = 0.7,
    *,
    client: DatabaseClient | None = None,
    embedder: Callable[[list[str]], list[list[float]]] = embed_texts,
) -> list[dict[str, Any]]:
    """Return deduplicated entries ranked by semantic and exact-match relevance.

    ``weight`` is the semantic contribution: zero performs only full-text search
    and one performs only vector similarity search.  The database functions keep
    pgvector and tsvector implementation details out of consumer surfaces.
    """
    _validate_search_arguments(query, top_k, weight)
    database = client or create_supabase_client()
    candidate_count = max(top_k * 3, 15)
    semantic_rows: list[dict[str, Any]] = []
    exact_rows: list[dict[str, Any]] = []

    if weight > 0:
        embeddings = embedder([query])
        if len(embeddings) != 1:
            raise ValueError("Embedding provider returned an unexpected number of vectors")
        semantic_rows = _response_rows(
            database.rpc(
                "match_entries_by_embedding",
                {"query_embedding": embeddings[0], "match_count": candidate_count},
            ).execute()
        )
    if weight < 1:
        exact_rows = _response_rows(
            database.rpc(
                "match_entries_by_text",
                {"search_query": query, "match_count": candidate_count},
            ).execute()
        )

    trigger_words = _trigger_words(database)
    return _blend_results(semantic_rows, exact_rows, weight, trigger_words, top_k)


def _validate_search_arguments(query: str, top_k: int, weight: float) -> None:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must contain non-whitespace text")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
        raise ValueError("top_k must be a positive integer")
    if isinstance(weight, bool) or not isinstance(weight, (int, float)) or not 0 <= weight <= 1:
        raise ValueError("weight must be between 0.0 and 1.0")


def _response_rows(response: Any) -> list[dict[str, Any]]:
    rows = getattr(response, "data", None) or []
    if not isinstance(rows, list):
        raise ValueError("Database search returned an invalid response")
    return [row for row in rows if isinstance(row, dict)]


def _trigger_words(database: DatabaseClient) -> list[str]:
    response = database.table("trigger_words").select("word").execute()
    rows = _response_rows(response)
    return [word.strip() for row in rows if isinstance((word := row.get("word")), str) and word.strip()]


def _blend_results(
    semantic_rows: Iterable[dict[str, Any]],
    exact_rows: Iterable[dict[str, Any]],
    weight: float,
    trigger_words: Iterable[str],
    top_k: int,
) -> list[dict[str, Any]]:
    combined: dict[str, dict[str, Any]] = {}
    for row in semantic_rows:
        _add_component(combined, row, "semantic_score")
    for row in exact_rows:
        _add_component(combined, row, "exact_score")

    matchers = [_trigger_matcher(word) for word in trigger_words]
    results: list[dict[str, Any]] = []
    for values in combined.values():
        content = str(values.get("content") or "")
        score = weight * values["semantic_score"] + (1 - weight) * values["exact_score"]
        if any(matcher.search(content) for matcher in matchers):
            score += DEFAULT_TRIGGER_WORD_BONUS
        result = {field: values.get(field) for field in RESULT_FIELDS}
        result["blended_score"] = score
        results.append(result)
    return sorted(results, key=lambda item: (-item["blended_score"], str(item["id"])))[:top_k]


def _add_component(combined: dict[str, dict[str, Any]], row: dict[str, Any], score_field: str) -> None:
    entry_id = row.get("id")
    if entry_id is None:
        raise ValueError("Database search returned an entry without an id")
    entry = combined.setdefault(str(entry_id), {"semantic_score": 0.0, "exact_score": 0.0})
    entry.update({field: row.get(field) for field in RESULT_FIELDS if field in row})
    score = row.get(score_field, 0)
    if not isinstance(score, (int, float)):
        raise ValueError(f"Database search returned an invalid {score_field}")
    entry[score_field] = float(score)


def _trigger_matcher(word: str) -> re.Pattern[str]:
    return re.compile(r"(?<!\\w)" + re.escape(word) + r"(?!\\w)", re.IGNORECASE)
