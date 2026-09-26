from __future__ import annotations

from typing import Any

from api import main
from tests.helpers import asgi_request


class Response:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.data = rows


class Query:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def __getattr__(self, name: str) -> Any:
        def method(*args: Any, **kwargs: Any) -> Query:
            self.calls.append((name, args, kwargs))
            return self
        return method

    def execute(self) -> Response:
        self.calls.append(("execute", (), {}))
        return Response(self.rows)


class Database:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.queries: list[Query] = []

    def table(self, name: str) -> Query:
        assert name in {"entries", "retrieval_logs"}
        query = Query(self.rows)
        self.queries.append(query)
        return query


def test_search_delegates_to_the_shared_mcp_boundary(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        main.knowledge_base,
        "search_entries",
        lambda query, top_k, weight: {"log_id": "log-1", "results": [{"id": query, "top_k": top_k, "weight": weight}]},
    )
    response = asgi_request(main.app, "POST", "/search", json={"query": "reverse honeypot", "top_k": 2, "weight": 0.5})
    assert response.status_code == 200
    assert response.json()["results"] == [{"id": "reverse honeypot", "top_k": 2, "weight": 0.5}]


def test_entries_support_combined_filters_and_newest_first(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setattr(main.knowledge_base, "list_entries", lambda **kwargs: captured.update(kwargs) or [{"id": "entry-1"}])
    response = asgi_request(
        main.app,
        "GET",
        "/entries?tag=cybersecurity&start=2026-09-01T00:00:00Z&end=2026-09-30T00:00:00Z&source_type=notion_note"
    )
    assert response.status_code == 200
    assert response.json() == [{"id": "entry-1"}]
    assert captured == {
        "tag": "cybersecurity", "start": "2026-09-01T00:00:00+00:00",
        "end": "2026-09-30T00:00:00+00:00", "source_type": "notion_note",
    }


def test_context_ingest_and_trigger_words_delegate_to_existing_operations(monkeypatch: Any) -> None:
    monkeypatch.setattr(main.knowledge_base, "get_entry_context", lambda entry_id: [{"id": entry_id}])
    monkeypatch.setattr(main.knowledge_base, "ingest_entry", lambda text, source_type, recorded_at: {"content": text, "source_type": source_type, "recorded_at": recorded_at})
    monkeypatch.setattr(main.knowledge_base, "list_trigger_words", lambda: [{"word": "mass-time"}])
    monkeypatch.setattr(main.knowledge_base, "add_trigger_word", lambda word: {"word": word.strip(), "already_exists": False, "count": 1})
    monkeypatch.setattr(main.knowledge_base, "remove_trigger_word", lambda word: {"word": word.strip(), "count": 0})
    assert asgi_request(main.app, "GET", "/entries/entry-1/context").json() == [{"id": "entry-1"}]
    assert asgi_request(main.app, "POST", "/ingest", json={"text": "A journal thought", "source_type": "notion_note"}).status_code == 200
    assert asgi_request(main.app, "GET", "/trigger-words").json() == [{"word": "mass-time"}]
    assert asgi_request(main.app, "POST", "/trigger-words", json={"word": " new term "}).json()["word"] == "new term"
    assert asgi_request(main.app, "DELETE", "/trigger-words/new%20term").json()["word"] == "new term"


def test_entry_audio_uses_the_entry_source_from_the_shared_boundary(monkeypatch: Any) -> None:
    monkeypatch.setattr(
        main.knowledge_base,
        "get_entry_context",
        lambda entry_id: [{"id": entry_id, "source_file": "README.md"}],
    )
    response = asgi_request(main.app, "GET", "/entries/entry-1/audio")
    assert response.status_code == 200
    assert "Local setup" in response.text


def test_retrieval_logs_are_limited_and_sorted(monkeypatch: Any) -> None:
    database = Database([{"id": "log-1"}])
    monkeypatch.setattr(main, "create_supabase_client", lambda: database)
    response = asgi_request(main.app, "GET", "/retrieval-logs?limit=10")
    assert response.status_code == 200
    calls = database.queries[0].calls
    assert ("order", ("created_at",), {"desc": True}) in calls
    assert ("limit", (10,), {}) in calls


def test_domain_validation_becomes_a_bad_request(monkeypatch: Any) -> None:
    monkeypatch.setattr(main.knowledge_base, "get_entry_context", lambda _: (_ for _ in ()).throw(ValueError("No entry exists")))
    response = asgi_request(main.app, "GET", "/entries/missing/context")
    assert response.status_code == 400
    assert response.json()["detail"] == "No entry exists"


def test_journal_inventory_actions_and_review_routes(monkeypatch: Any) -> None:
    monkeypatch.setattr(main, "create_supabase_client", lambda: object())
    monkeypatch.setattr(main, "list_journals", lambda *, client: [{"journal_name": "Friday"}])
    monkeypatch.setattr(main, "get_journal_context", lambda source_file, *, client: [{"source_file": source_file, "id": "chunk-1"}])
    monkeypatch.setattr(main, "list_action_items", lambda status=None, *, client: [{"id": "action-1", "status": status or "suggested"}])
    monkeypatch.setattr(main, "review_action_item", lambda action_id, status, *, client: {"id": action_id, "status": status})
    async def extract(**_: Any) -> dict[str, int]: return {"journals_processed": 1, "suggestions_found": 1, "journals_skipped": 0}
    monkeypatch.setattr(main, "extract_current_journals", extract)
    assert asgi_request(main.app, "GET", "/journals").json() == [{"journal_name": "Friday"}]
    assert asgi_request(main.app, "GET", "/journals/context?source_file=Friday.json").json()[0]["id"] == "chunk-1"
    assert asgi_request(main.app, "GET", "/journal-actions?status=suggested").json()[0]["status"] == "suggested"
    assert asgi_request(main.app, "POST", "/journal-actions/action-1/review", json={"status": "approved"}).json()["status"] == "approved"
    assert asgi_request(main.app, "POST", "/journal-actions/extract", json={}).json()["suggestions_found"] == 1
