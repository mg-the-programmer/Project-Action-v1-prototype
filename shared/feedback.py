"""Persistence helpers for retrieval feedback and evaluation exports."""
from __future__ import annotations

import json
from typing import Any, Protocol

from shared.clients import create_supabase_client


class FeedbackDatabase(Protocol):
    """The small Supabase surface used for retrieval feedback."""

    def table(self, table_name: str) -> Any: ...


def log_retrieval(
    query: str,
    results: list[dict[str, Any]],
    *,
    rating: int | None = None,
    comment: str | None = None,
    client: FeedbackDatabase | None = None,
) -> str:
    """Store one retrieval interaction and return its database log id."""
    _validate_query(query)
    _validate_results(results)
    _validate_rating(rating, required=False)
    _validate_comment(comment)
    payload: dict[str, Any] = {"query": query.strip(), "results": results}
    if rating is not None:
        payload["rating"] = rating
    if comment is not None:
        payload["comment"] = comment.strip()
    database = client or create_supabase_client()
    rows = database.table("retrieval_logs").insert(payload).select("id").execute().data or []
    if not rows or not isinstance(rows[0].get("id"), str):
        raise RuntimeError("Retrieval log insert did not return an id")
    return rows[0]["id"]


def rate_retrieval(
    log_id: str,
    rating: int,
    comment: str,
    *,
    client: FeedbackDatabase | None = None,
) -> str:
    """Annotate a recorded retrieval, rejecting unknown log ids."""
    if not isinstance(log_id, str) or not log_id.strip():
        raise ValueError("log_id must contain non-whitespace text")
    _validate_rating(rating, required=True)
    _validate_comment(comment, required=True)
    database = client or create_supabase_client()
    rows = (
        database.table("retrieval_logs")
        .update({"rating": rating, "comment": comment.strip()})
        .eq("id", log_id.strip())
        .select("id")
        .execute()
        .data
        or []
    )
    if not rows:
        raise ValueError("No retrieval log exists for the supplied log_id")
    return str(rows[0]["id"])


def _validate_query(query: str) -> None:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must contain non-whitespace text")


def _validate_results(results: list[dict[str, Any]]) -> None:
    if not isinstance(results, list) or not all(isinstance(result, dict) for result in results):
        raise ValueError("results must be a list of result objects")
    try:
        json.dumps(results)
    except (TypeError, ValueError) as error:
        raise ValueError("results must be JSON serializable") from error


def _validate_rating(rating: int | None, *, required: bool) -> None:
    if rating is None and not required:
        return
    if isinstance(rating, bool) or not isinstance(rating, int) or not 1 <= rating <= 5:
        raise ValueError("rating must be an integer between 1 and 5")


def _validate_comment(comment: str | None, *, required: bool = False) -> None:
    if comment is None and not required:
        return
    if not isinstance(comment, str) or (required and not comment.strip()):
        raise ValueError("comment must contain non-whitespace text")
