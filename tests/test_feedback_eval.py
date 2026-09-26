from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from eval import export_pairs
from eval.export_pairs import dataset_pairs, write_pairs
from shared.feedback import log_retrieval, rate_retrieval


class Response:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.data = rows

    def execute(self) -> Response:
        return self


class Query:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, Any]] = []

    def insert(self, payload: dict[str, Any]) -> Query:
        self.calls.append(("insert", payload))
        return self

    def update(self, payload: dict[str, Any]) -> Query:
        self.calls.append(("update", payload))
        return self

    def eq(self, field: str, value: str) -> Query:
        self.calls.append(("eq", (field, value)))
        return self

    def select(self, fields: str) -> Query:
        self.calls.append(("select", fields))
        return self

    def execute(self) -> Response:
        return Response(self.rows)


class Database:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.query = Query(rows)

    def table(self, name: str) -> Query:
        assert name == "retrieval_logs"
        return self.query


def test_log_retrieval_stores_json_results_and_returns_id() -> None:
    database = Database([{"id": "log-id"}])
    assert log_retrieval("a query", [{"id": "entry-id"}], client=database) == "log-id"
    assert database.query.calls[0] == ("insert", {"query": "a query", "results": [{"id": "entry-id"}]})


def test_rate_retrieval_updates_a_matching_row() -> None:
    database = Database([{"id": "log-id"}])
    assert rate_retrieval("log-id", 2, "missed it", client=database) == "log-id"
    assert ("update", {"rating": 2, "comment": "missed it"}) in database.query.calls
    with pytest.raises(ValueError, match="rating"):
        rate_retrieval("log-id", 6, "bad", client=database)


def test_rate_retrieval_rejects_unknown_log() -> None:
    with pytest.raises(ValueError, match="No retrieval"):
        rate_retrieval("missing", 3, "okay", client=Database([]))


def test_dataset_pairs_preserve_feedback_without_inventing_expected_ids(tmp_path: Path) -> None:
    pairs = dataset_pairs([{
        "query": "reverse honeypot", "results": [{"id": "entry-1"}], "rating": 2, "comment": "missed context",
    }])
    assert pairs == [{
        "query": "reverse honeypot", "expected_entry_ids": [], "actual_results": [{"id": "entry-1"}],
        "rating": 2, "comment": "missed context",
    }]
    output = write_pairs(tmp_path / "pairs.json", pairs)
    assert json.loads(output.read_text(encoding="utf-8")) == pairs


def test_export_push_defaults_dataset_name_to_configured_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: list[str] = []
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-only")
    monkeypatch.setenv("LANGSMITH_PROJECT", "personal-kb")
    monkeypatch.setattr(export_pairs, "load_environment_file", lambda _: None)
    monkeypatch.setattr(export_pairs, "rated_logs", lambda: [])
    monkeypatch.setattr(export_pairs, "write_pairs", lambda output, pairs: tmp_path / "pairs.json")
    monkeypatch.setattr(
        export_pairs,
        "push_pairs_to_langsmith",
        lambda pairs, dataset_name: captured.append(dataset_name) or len(pairs),
    )
    monkeypatch.setattr("sys.argv", ["export_pairs", "--push"])
    assert export_pairs.main() == 0
    assert captured == ["personal-kb"]
