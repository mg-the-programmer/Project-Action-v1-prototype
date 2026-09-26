from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from scripts.transcribe import REPOSITORY_ROOT, load_environment_file
from shared.clients import create_supabase_client
from shared.retrieval import search_entries


class Response:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.data = rows

    def execute(self) -> Response:
        return self


class FakeDatabase:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def rpc(self, function_name: str, parameters: dict[str, Any]) -> Response:
        self.calls.append((function_name, parameters))
        if function_name == "match_entries_by_embedding":
            return Response([
                _entry("semantic", "A conceptual teaching note", semantic_score=0.9),
                _entry("trigger", "My reverse honeypot teaching analogy", semantic_score=0.7),
            ])
        return Response([
            _entry("trigger", "My reverse honeypot teaching analogy", exact_score=0.4),
            _entry("exact", "A honeypot is a security teaching example", exact_score=0.8),
        ])

    def table(self, table_name: str) -> FakeDatabase:
        assert table_name == "trigger_words"
        return self

    def select(self, columns: str) -> Response:
        assert columns == "word"
        return Response([{"word": "reverse honeypot"}])


def _entry(entry_id: str, content: str, **score: float) -> dict[str, Any]:
    return {
        "id": entry_id,
        "content": content,
        "source_type": "voice_memo",
        "source_file": "journal.m4a",
        "audio_offset": 12.5,
        "tags": ["cybersecurity"],
        "mood": "curious",
        "topic_label": "cybersecurity",
        "moment_type": "idea",
        "visual_context": None,
        "recorded_at": "2026-09-26T00:00:00+00:00",
        **score,
    }


def test_search_blends_deduplicates_and_boosts_trigger_words() -> None:
    database = FakeDatabase()
    results = search_entries("honeypot teaching", top_k=3, client=database, embedder=lambda _: [[0.0] * 1536])
    assert [result["id"] for result in results] == ["trigger", "semantic", "exact"]
    assert results[0]["blended_score"] == pytest.approx(0.76)
    assert set(results[0]) == {
        "id", "content", "source_type", "source_file", "audio_offset", "tags", "mood",
        "topic_label", "moment_type", "visual_context", "recorded_at", "blended_score",
    }
    assert [call[0] for call in database.calls] == ["match_entries_by_embedding", "match_entries_by_text"]


def test_weight_extremes_call_only_the_selected_retrieval_mode() -> None:
    exact_database = FakeDatabase()
    exact_results = search_entries("honeypot", weight=0.0, client=exact_database)
    assert [call[0] for call in exact_database.calls] == ["match_entries_by_text"]
    assert [result["id"] for result in exact_results] == ["exact", "trigger"]

    semantic_database = FakeDatabase()
    semantic_results = search_entries("honeypot", weight=1.0, client=semantic_database, embedder=lambda _: [[0.0] * 1536])
    assert [call[0] for call in semantic_database.calls] == ["match_entries_by_embedding"]
    assert [result["id"] for result in semantic_results] == ["semantic", "trigger"]


def test_search_rejects_invalid_arguments() -> None:
    with pytest.raises(ValueError, match="query"):
        search_entries(" ", client=FakeDatabase())
    with pytest.raises(ValueError, match="top_k"):
        search_entries("valid", top_k=0, client=FakeDatabase())
    with pytest.raises(ValueError, match="weight"):
        search_entries("valid", weight=1.1, client=FakeDatabase())


def test_retrieval_result_shape_accepts_an_ignored_voice_journal_sample() -> None:
    sample_path = REPOSITORY_ROOT / "datasets" / "voice_journals" / "Life Journey.pause.chunks.json"
    if not sample_path.exists():
        pytest.skip("Ignored voice-journal dataset is not available")
    sample = json.loads(sample_path.read_text(encoding="utf-8"))[0]
    database = FakeDatabase()
    database.rpc = lambda function_name, parameters: Response(  # type: ignore[method-assign]
        [{**sample, "id": "sample", "semantic_score": 0.9}]
        if function_name.endswith("embedding")
        else []
    )
    result = search_entries("life journey", weight=1.0, client=database, embedder=lambda _: [[0.0] * 1536])[0]
    assert result["content"] == sample["content"]
    assert result["source_file"] == sample["source_file"]


@pytest.mark.integration
def test_live_database_exact_search_returns_a_known_entry() -> None:
    """Run only after applying this ticket's migration: no records are written."""
    load_environment_file(REPOSITORY_ROOT / ".env")
    if os.environ.get("RUN_LIVE_SUPABASE_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_SUPABASE_TESTS=1 to query the configured Supabase database")
    database = create_supabase_client()
    known = database.table("entries").select("id, content").limit(1).execute().data
    if not known:
        pytest.skip("Configured database has no entries to retrieve")
    entry = known[0]
    query = " ".join(str(entry["content"]).split()[:6])
    results = search_entries(query, top_k=15, weight=0.0, client=database)
    assert entry["id"] in {result["id"] for result in results}
