from __future__ import annotations

import asyncio
from typing import Any

from scripts.extract_actions import extract_current_journals, valid_actions
from shared import journal_actions


class Response:
    def __init__(self, data: list[dict[str, Any]]) -> None:
        self.data = data


class Query:
    def __init__(self, database: FakeDatabase, table: str) -> None:
        self.database, self.table, self.filters = database, table, []
        self.values: dict[str, Any] | list[dict[str, Any]] | None = None
        self.conflict = ""

    def select(self, *_: Any) -> Query: return self
    def order(self, *_: Any, **__: Any) -> Query: return self
    def eq(self, field: str, value: Any) -> Query: self.filters.append((field, value)); return self
    def in_(self, field: str, values: list[Any]) -> Query: self.filters.append((field, values)); return self
    def update(self, values: dict[str, Any]) -> Query: self.values = values; return self
    def upsert(self, values: dict[str, Any] | list[dict[str, Any]], *, on_conflict: str) -> Query: self.values, self.conflict = values, on_conflict; return self

    def execute(self) -> Response:
        rows = self.database.tables.setdefault(self.table, [])
        if self.values is not None and isinstance(self.values, dict) and self.table == "journal_action_items":
            matched = [row for row in rows if all(row.get(key) == value for key, value in self.filters)]
            for row in matched: row.update(self.values)
            return Response(matched)
        if self.values is not None:
            pending = self.values if isinstance(self.values, list) else [self.values]
            for item in pending:
                existing = next((row for row in rows if row.get("source_file") == item.get("source_file") and (row.get("action_key") == item.get("action_key") or self.table == "journal_action_extractions")), None)
                if existing: existing.update(item)
                else: rows.append(dict(item))
            return Response(pending)
        return Response([row for row in rows if all(row.get(key) in value if isinstance(value, list) else row.get(key) == value for key, value in self.filters)])


class FakeDatabase:
    def __init__(self, tables: dict[str, list[dict[str, Any]]]) -> None: self.tables = tables
    def table(self, name: str) -> Query: return Query(self, name)


def test_inventory_prefers_pause_and_groups_source_metadata() -> None:
    client = FakeDatabase({"entries": [
        {"id": "a", "source_file": "voice/Friday.json", "source_type": "voice_memo", "chunk_index": 0, "chunk_strategy": "pause", "content": "one", "tags": ["personal"], "topic_label": "personal-growth", "recorded_at": "2026-09-20T10:00:00Z"},
        {"id": "b", "source_file": "voice/Friday.json", "source_type": "voice_memo", "chunk_index": 1, "chunk_strategy": "pause", "content": "two", "tags": ["business"], "topic_label": "business-ideas", "recorded_at": "2026-09-20T10:10:00Z"},
        {"id": "semantic", "source_file": "voice/Friday.json", "source_type": "voice_memo", "chunk_index": 0, "chunk_strategy": "semantic", "content": "duplicate", "tags": [], "recorded_at": "2026-09-20T10:00:00Z"},
    ]})
    journals = journal_actions.list_journals(client=client)
    assert journals == [{"source_file": "voice/Friday.json", "journal_name": "Friday", "recorded_start": "2026-09-20T10:00:00Z", "recorded_end": "2026-09-20T10:10:00Z", "chunk_count": 2, "tags": ["business", "personal"], "labels": ["business-ideas", "personal-growth"]}]
    assert [item["id"] for item in journal_actions.get_journal_context("voice/Friday.json", client=client)] == ["a", "b"]


def test_action_validation_rejects_unsupported_evidence() -> None:
    chunks = [{"id": "a", "chunk_index": 2, "content": "I need to email the editor on Monday."}]
    actions = valid_actions([
        {"wording": "Email the editor", "source_chunk_index": 2, "evidence": "email the editor"},
        {"wording": "Invent a task", "source_chunk_index": 2, "evidence": "not in source"},
        {"wording": "Book a flight", "source_chunk_index": 2, "evidence": "email the editor"},
    ], chunks)
    assert len(actions) == 1
    assert actions[0]["source_entry_id"] == "a"


def test_explicit_extraction_is_idempotent_for_unchanged_journal() -> None:
    client = FakeDatabase({"entries": [{"id": "a", "source_file": "memo.json", "source_type": "voice_memo", "chunk_index": 0, "chunk_strategy": "pause", "content": "I will call the accountant tomorrow."}], "journal_action_items": [], "journal_action_extractions": []})
    calls = 0
    async def extractor(_: list[dict[str, Any]]) -> list[dict[str, Any]]:
        nonlocal calls
        calls += 1
        return [{"wording": "Call the accountant", "source_chunk_index": 0, "evidence": "call the accountant tomorrow"}]
    first = asyncio.run(extract_current_journals(client=client, extractor=extractor))
    second = asyncio.run(extract_current_journals(client=client, extractor=extractor))
    assert first == {"journals_processed": 1, "suggestions_found": 1, "journals_skipped": 0}
    assert second == {"journals_processed": 0, "suggestions_found": 0, "journals_skipped": 1}
    assert calls == 1
    assert len(client.tables["journal_action_items"]) == 1
