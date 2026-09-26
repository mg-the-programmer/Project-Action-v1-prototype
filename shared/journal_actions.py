"""Journal inventory and local-only action suggestion storage."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol

JOURNAL_FIELDS = "id,content,source_file,chunk_index,chunk_strategy,tags,topic_label,recorded_at"
ACTION_FIELDS = "id,source_file,source_entry_id,wording,evidence,status,extracted_at,reviewed_at,created_at"
ACTION_STATUSES = {"suggested", "approved", "dismissed"}


class Database(Protocol):
    def table(self, name: str) -> Any: ...


def canonical_journal_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Prefer pause chunks for a source, avoiding duplicate strategy inventory."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        source_file = row.get("source_file")
        if isinstance(source_file, str) and source_file:
            grouped[source_file].append(row)
    canonical: list[dict[str, Any]] = []
    for source_rows in grouped.values():
        pause_rows = [row for row in source_rows if row.get("chunk_strategy") == "pause"]
        canonical.extend(pause_rows or source_rows)
    return canonical


def list_journals(*, client: Database) -> list[dict[str, Any]]:
    rows = (
        client.table("entries").select(JOURNAL_FIELDS).eq("source_type", "voice_memo")
        .order("source_file").order("chunk_index").execute().data or []
    )
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in canonical_journal_rows(rows):
        grouped[row["source_file"]].append(row)
    journals: list[dict[str, Any]] = []
    for source_file, chunks in grouped.items():
        dates = sorted(str(row["recorded_at"]) for row in chunks if row.get("recorded_at"))
        tags = sorted({tag for row in chunks for tag in (row.get("tags") or []) if isinstance(tag, str)})
        labels = sorted({str(row["topic_label"]) for row in chunks if row.get("topic_label")})
        journals.append({
            "source_file": source_file,
            "journal_name": _journal_name(source_file),
            "recorded_start": dates[0] if dates else None,
            "recorded_end": dates[-1] if dates else None,
            "chunk_count": len(chunks),
            "tags": tags,
            "labels": labels,
        })
    return sorted(journals, key=lambda item: item["recorded_end"] or "", reverse=True)


def get_journal_context(source_file: str, *, client: Database) -> list[dict[str, Any]]:
    if not source_file.strip():
        raise ValueError("source_file is required")
    rows = (
        client.table("entries").select(JOURNAL_FIELDS).eq("source_type", "voice_memo")
        .eq("source_file", source_file).order("chunk_index").execute().data or []
    )
    context = canonical_journal_rows(rows)
    if not context:
        raise ValueError("No voice-memo journal exists for the supplied source file")
    return context


def list_action_items(status: str | None = None, *, client: Database) -> list[dict[str, Any]]:
    if status is not None and status not in ACTION_STATUSES:
        raise ValueError("status must be suggested, approved, or dismissed")
    query = client.table("journal_action_items").select(ACTION_FIELDS)
    if status is not None:
        query = query.eq("status", status)
    return query.order("created_at", desc=True).execute().data or []


def review_action_item(action_id: str, status: str, *, client: Database) -> dict[str, Any]:
    if not action_id.strip():
        raise ValueError("action id is required")
    if status not in {"approved", "dismissed"}:
        raise ValueError("status must be approved or dismissed")
    rows = (
        client.table("journal_action_items")
        .update({"status": status, "reviewed_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", action_id).execute().data or []
    )
    if not rows:
        raise ValueError("No action item exists for the supplied id")
    return rows[0]


def journal_fingerprint(chunks: list[dict[str, Any]]) -> str:
    payload = "\n".join(
        f"{item.get('id','')}:{item.get('chunk_index','')}:{item.get('content','')}"
        for item in sorted(chunks, key=lambda item: (item.get("chunk_index", -1), str(item.get("id", ""))))
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def action_key(source_entry_id: str, wording: str) -> str:
    return sha256(f"{source_entry_id}:{' '.join(wording.lower().split())}".encode("utf-8")).hexdigest()


def _journal_name(source_file: str) -> str:
    name = Path(source_file).name
    return name.removesuffix(".json") or source_file
