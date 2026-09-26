from __future__ import annotations

import asyncio
from typing import Any

import pytest

from mcp_server import server


class Response:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.data = rows

    def execute(self) -> Response:
        return self


class Query:
    def __init__(self, response: Response) -> None:
        self.response = response
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def __getattr__(self, name: str) -> Any:
        def method(*args: Any, **kwargs: Any) -> Query:
            self.calls.append((name, args, kwargs))
            return self
        return method

    def execute(self) -> Response:
        self.calls.append(("execute", (), {}))
        return self.response


class FakeDatabase:
    def __init__(self, responses: list[Response]) -> None:
        self.responses = iter(responses)
        self.queries: list[Query] = []

    def table(self, table_name: str) -> Query:
        assert table_name in {"entries", "retrieval_logs", "trigger_words"}
        query = Query(next(self.responses))
        self.queries.append(query)
        return query


def test_registers_core_feedback_and_trigger_word_tools() -> None:
    tools = asyncio.run(server.server.list_tools())
    assert {tool.name for tool in tools} == {
        "search_entries", "get_entry_context", "list_by_tag", "list_by_date_range", "ingest_entry",
        "log_feedback", "rate_retrieval", "add_trigger_word", "list_trigger_words", "journal_and_recall",
    }


def test_get_entry_context_limits_to_adjacent_chunks_in_the_same_source() -> None:
    database = FakeDatabase([
        Response([{"source_file": "memo.m4a", "chunk_index": 3, "chunk_strategy": "pause"}]),
        Response([{"id": "before"}, {"id": "target"}, {"id": "after"}]),
    ])

    assert server.get_entry_context("target", client=database) == [
        {"id": "before"}, {"id": "target"}, {"id": "after"}
    ]
    calls = database.queries[1].calls
    assert ("eq", ("source_file", "memo.m4a"), {}) in calls
    assert not any(call[0] == "eq" and call[1][0] == "chunk_strategy" for call in calls)
    assert ("gte", ("chunk_index", 2), {}) in calls
    assert ("lte", ("chunk_index", 4), {}) in calls
    assert ("order", ("chunk_index",), {}) in calls


def test_list_tools_filter_and_order_entries() -> None:
    tag_database = FakeDatabase([Response([{"id": "tagged"}])])
    assert server.list_by_tag("cybersecurity", client=tag_database) == [{"id": "tagged"}]
    assert ("contains", ("tags", ["cybersecurity"]), {}) in tag_database.queries[0].calls
    assert ("order", ("recorded_at",), {"desc": True}) in tag_database.queries[0].calls

    date_database = FakeDatabase([Response([{"id": "dated"}])])
    assert server.list_by_date_range(
        "2026-09-01T00:00:00+00:00", "2026-09-30T00:00:00+00:00", client=date_database
    ) == [{"id": "dated"}]
    assert ("gte", ("recorded_at", "2026-09-01T00:00:00+00:00"), {}) in date_database.queries[0].calls
    assert ("lte", ("recorded_at", "2026-09-30T00:00:00+00:00"), {}) in date_database.queries[0].calls


def test_ingest_entry_enriches_and_stores_a_single_chunk(monkeypatch: pytest.MonkeyPatch) -> None:
    stored: list[dict[str, Any]] = []
    database = object()

    def fake_store(chunks: list[dict[str, Any]], client: Any) -> int:
        assert client is database
        stored.extend(chunks)
        return 1

    async def fake_tagger(_: str) -> dict[str, Any]:
        return {"tags": ["daily-journal"], "mood": "reflective", "topic_label": "personal-growth",
                "moment_type": "reflection", "visual_context": None}

    monkeypatch.setattr(server, "store_chunks", fake_store)
    monkeypatch.setattr(server, "_stored_entry_id", lambda *_: "stored-entry")
    result = server.ingest_entry(
        "Today I learned to leave room for reflection.", "notion_note", "2026-09-26T10:00:00+00:00",
        client=database, embedder=lambda _: [[0.5] * 1536], tagger=fake_tagger,
    )

    assert result.items() >= stored[0].items()
    assert isinstance(result["id"], str)
    assert result["source_type"] == "notion_note"
    assert result["chunk_strategy"] == "heading"
    assert result["recorded_at"] == "2026-09-26T10:00:00+00:00"
    assert result["tags"] == ["daily-journal"]
    assert len(result["embedding"]) == 1536


def test_ingest_entry_validates_the_database_contract() -> None:
    with pytest.raises(ValueError, match="source_type"):
        server.ingest_entry("a journal", "journal")
    with pytest.raises(ValueError, match="ISO-8601"):
        server.list_by_date_range("September", "2026-09-30")


def test_ingest_entry_uses_the_default_voice_memo_chunk_strategy(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_tagger(_: str) -> dict[str, Any]:
        return {"tags": [], "mood": "neutral", "topic_label": "random", "moment_type": None, "visual_context": None}

    monkeypatch.setattr(server, "store_chunks", lambda chunks, client: 1)
    monkeypatch.setattr(server, "_stored_entry_id", lambda *_: "stored-entry")
    result = server.ingest_entry(
        "A spoken reflection.", "voice_memo", client=object(), embedder=lambda _: [[0.5] * 1536], tagger=fake_tagger
    )
    assert result["chunk_strategy"] == "pause"


def test_ingest_entry_uses_the_current_time_when_recorded_at_is_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_tagger(_: str) -> dict[str, Any]:
        return {"tags": [], "mood": "neutral", "topic_label": "random", "moment_type": None, "visual_context": None}

    monkeypatch.setattr(server, "store_chunks", lambda chunks, client: 1)
    monkeypatch.setattr(server, "_stored_entry_id", lambda *_: "stored-entry")
    result = server.ingest_entry(
        "A direct journal entry.", "notion_note", client=object(), embedder=lambda _: [[0.5] * 1536], tagger=fake_tagger
    )
    assert result["recorded_at"] is not None
    assert server._parse_datetime(result["recorded_at"]).tzinfo is not None


def test_search_entries_logs_results_and_returns_the_log_id(monkeypatch: pytest.MonkeyPatch) -> None:
    database = object()
    monkeypatch.setattr(server, "create_supabase_client", lambda: database)
    monkeypatch.setattr(server, "retrieve_entries", lambda *args, **kwargs: [{"id": "entry-1"}])
    calls: list[tuple[str, list[dict[str, Any]], Any]] = []
    monkeypatch.setattr(
        server, "log_retrieval",
        lambda query, results, client: calls.append((query, results, client)) or "log-1",
    )
    assert server.search_entries("security teaching") == {
        "log_id": "log-1", "results": [{"id": "entry-1"}]
    }
    assert calls == [("security teaching", [{"id": "entry-1"}], database)]


def test_journal_and_recall_returns_only_past_entries_and_logs_them(monkeypatch: pytest.MonkeyPatch) -> None:
    database = object()

    async def fake_ingest(*args: Any, **kwargs: Any) -> dict[str, Any]:
        assert args[:3] == ("Today I refined my teaching analogy.", "notion_note", "2026-09-26T10:00:00+00:00")
        assert kwargs["client"] is database
        return {
            "id": "new-entry", "content": args[0], "recorded_at": args[2],
            "tags": ["daily-journal"], "mood": "reflective", "topic_label": "personal-growth",
            "moment_type": "reflection",
        }

    monkeypatch.setattr(server, "_ingest_entry", fake_ingest)
    logged: list[tuple[str, list[dict[str, Any]], Any]] = []
    monkeypatch.setattr(
        server,
        "log_retrieval",
        lambda query, results, client: logged.append((query, results, client)) or "recall-log",
    )
    results = [
        {"id": "new-entry", "content": "Today I refined my teaching analogy."},
        {
            "id": "older-entry", "source_file": "memo.m4a", "recorded_at": "2026-09-20T08:00:00+00:00",
            "mood": "curious", "content": "An older note about the same analogy.", "blended_score": 0.81,
        },
    ]
    retrieval_calls: list[dict[str, Any]] = []

    def fake_retriever(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
        retrieval_calls.append(kwargs)
        return results

    response = asyncio.run(
        server.journal_and_recall(
            "Today I refined my teaching analogy.",
            "2026-09-26T10:00:00+00:00",
            client=database,
            retriever=fake_retriever,
        )
    )

    assert response["ingestion"]["id"] == "new-entry"
    assert response["log_id"] == "recall-log"
    assert response["related_past_entries"] == [{
        "rank": 1, "id": "older-entry", "source": "memo.m4a", "date": "2026-09-20T08:00:00+00:00",
        "mood": "curious", "content_preview": "An older note about the same analogy.", "blended_score": 0.81,
    }]
    assert logged == [("Today I refined my teaching analogy.", [results[1]], database)]
    assert retrieval_calls == [{"top_k": 16, "client": database}]


def test_journal_and_recall_truncates_long_content_previews() -> None:
    assert server._content_preview("x" * 281) == ("x" * 277) + "..."


def test_feedback_tools_delegate_to_the_feedback_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server, "log_retrieval", lambda *args, **kwargs: "manual-log")
    monkeypatch.setattr(server, "rate_retrieval", lambda *args, **kwargs: "rated-log")
    assert server.log_feedback_tool("query", [{"id": "entry"}], 5, "useful") == {"log_id": "manual-log"}
    assert server.rate_retrieval_tool("log", 2, "wrong result") == {"log_id": "rated-log"}


def test_add_trigger_word_inserts_and_reports_the_current_list_size() -> None:
    database = FakeDatabase([
        Response([]), Response([{"word": "reverse honeypot"}]), Response([{"word": "reverse honeypot"}]),
    ])

    assert server.add_trigger_word(" reverse honeypot ", client=database) == {
        "word": "reverse honeypot", "already_exists": False, "count": 1,
    }
    assert ("eq", ("word", "reverse honeypot"), {}) in database.queries[0].calls
    assert ("upsert", ({"word": "reverse honeypot"},), {
        "on_conflict": "word", "ignore_duplicates": True,
    }) in database.queries[1].calls
    assert ("select", ("word",), {}) in database.queries[2].calls


def test_add_trigger_word_confirms_a_duplicate_without_inserting() -> None:
    database = FakeDatabase([
        Response([{"word": "reverse honeypot"}]),
        Response([{"word": "reverse honeypot"}, {"word": "mass-time"}]),
    ])

    assert server.add_trigger_word("reverse honeypot", client=database) == {
        "word": "reverse honeypot", "already_exists": True, "count": 2,
    }
    assert not any(call[0] == "upsert" for query in database.queries for call in query.calls)


def test_list_trigger_words_orders_by_newest_added_timestamp() -> None:
    database = FakeDatabase([Response([{"word": "mass-time", "added_at": "2026-09-26T12:00:00+00:00"}])])

    assert server.list_trigger_words(client=database) == [
        {"word": "mass-time", "added_at": "2026-09-26T12:00:00+00:00"}
    ]
    assert ("select", ("word,added_at",), {}) in database.queries[0].calls
    assert ("order", ("added_at",), {"desc": True}) in database.queries[0].calls
