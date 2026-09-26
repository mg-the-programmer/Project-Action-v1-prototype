"""Live HTTP smoke coverage for the local REST application."""
from __future__ import annotations

import os
from uuid import uuid4

import pytest

from api.main import app
from scripts.transcribe import REPOSITORY_ROOT, load_environment_file
from shared.clients import create_supabase_client
from tests.helpers import asgi_request

load_environment_file(REPOSITORY_ROOT / ".env")


@pytest.mark.integration
def test_rest_endpoints_against_the_configured_services() -> None:
    """Exercise every REST route and remove each test-created remote row."""
    required = ("SUPABASE_URL", "SUPABASE_KEY", "OPENAI_API_KEY")
    if not all(os.environ.get(name) for name in required):
        pytest.skip("configured Supabase and OpenAI-compatible provider are required")

    database = create_supabase_client()
    created_log_id: str | None = None
    created_source_file: str | None = None
    trigger_word = f"ticket-11-api-fixture-{uuid4()}"
    try:
        search = asgi_request(app, "POST", "/search", json={"query": "cybersecurity teaching", "top_k": 1})
        assert search.status_code == 200
        search_body = search.json()
        created_log_id = search_body["log_id"]
        assert isinstance(search_body["results"], list)

        entries = asgi_request(app, "GET", "/entries?source_type=notion_note")
        assert entries.status_code == 200
        assert isinstance(entries.json(), list)

        ingested = asgi_request(
            app,
            "POST",
            "/ingest",
            json={
                "text": "Ticket 11 API live-test fixture about a reverse honeypot teaching analogy.",
                "source_type": "notion_note",
                "recorded_at": "2026-09-26T12:00:00Z",
            },
        )
        assert ingested.status_code == 200
        created_source_file = ingested.json()["source_file"]
        listed_entries = asgi_request(app, "GET", "/entries?source_type=notion_note")
        assert listed_entries.status_code == 200
        assert any(row["source_file"] == created_source_file for row in listed_entries.json())
        stored_entry = (
            database.table("entries").select("id").eq("source_file", created_source_file).execute().data or []
        )
        assert len(stored_entry) == 1
        context = asgi_request(app, "GET", f"/entries/{stored_entry[0]['id']}/context")
        assert context.status_code == 200
        assert any(row["id"] == stored_entry[0]["id"] for row in context.json())

        assert asgi_request(app, "GET", "/trigger-words").status_code == 200
        added_trigger = asgi_request(app, "POST", "/trigger-words", json={"word": trigger_word})
        assert added_trigger.status_code == 200
        assert added_trigger.json()["word"] == trigger_word

        logs = asgi_request(app, "GET", "/retrieval-logs?limit=50")
        assert logs.status_code == 200
        assert any(row["id"] == created_log_id for row in logs.json())
    finally:
        if created_log_id:
            database.table("retrieval_logs").delete().eq("id", created_log_id).execute()
        if created_source_file:
            database.table("entries").delete().eq("source_file", created_source_file).execute()
        database.table("trigger_words").delete().eq("word", trigger_word).execute()
