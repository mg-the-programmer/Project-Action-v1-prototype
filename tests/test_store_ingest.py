from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import ingest
from scripts import store


class FakeQuery:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.conflict = ""

    def upsert(self, rows: list[dict[str, Any]], *, on_conflict: str) -> FakeQuery:
        self.rows, self.conflict = rows, on_conflict
        return self

    def execute(self) -> Any:
        return type("Response", (), {"data": self.rows})()


class FakeClient:
    def __init__(self) -> None:
        self.query = FakeQuery()

    def table(self, name: str) -> FakeQuery:
        assert name == "entries"
        return self.query


def test_store_upserts_only_database_fields_with_stable_key() -> None:
    client = FakeClient()
    count = store.store_chunks([{
        "content": "remember this", "source_type": "notion_note", "source_file": "ideas.md",
        "chunk_index": 0, "chunk_strategy": "heading", "suggested_tags": ["review-me"],
    }], client)
    assert count == 1
    assert client.query.conflict == "source_file,chunk_index,chunk_strategy"
    assert client.query.rows == [{"content": "remember this", "source_type": "notion_note", "source_file": "ideas.md", "chunk_index": 0, "chunk_strategy": "heading"}]


def test_store_rejects_chunks_without_a_stable_identity() -> None:
    try:
        store.store_chunks([{"content": "missing identity"}], FakeClient())
    except ValueError as error:
        assert "source_file" in str(error)
    else:
        raise AssertionError("Expected stable-identity validation")


def test_store_accepts_an_actual_pause_chunk_dataset_without_duplicate_identity() -> None:
    source = Path("datasets/voice_journals/Life Journey.pause.chunks.json")
    chunks = json.loads(source.read_text(encoding="utf-8"))[:3]
    client = FakeClient()
    assert store.store_chunks(chunks, client) == 3
    assert {tuple(row[key] for key in ("source_file", "chunk_index", "chunk_strategy")) for row in client.query.rows} == {
        tuple(chunk[key] for key in ("source_file", "chunk_index", "chunk_strategy")) for chunk in chunks
    }


def test_notes_ingestion_runs_all_remaining_steps_on_real_export_shape(tmp_path: Path, monkeypatch: Any) -> None:
    note = tmp_path / "ideas.md"
    note.write_text("# Ideas\n\n## Recall\nA reverse honeypot teaching analogy.", encoding="utf-8")
    client = FakeClient()
    monkeypatch.setattr(ingest.embed, "embed_file", lambda path: (path, _add_embeddings(path)))
    async def fake_tag_file(path: Path) -> tuple[Path, int]:
        return _tag_file(path)

    monkeypatch.setattr(ingest.tag, "tag_file", fake_tag_file)
    result = ingest.ingest_notes(tmp_path, client=client)
    assert result == {"files_processed": 1, "chunks_created": 1, "chunks_embedded": 1, "chunks_tagged": 1, "entries_upserted": 1}
    assert client.query.rows[0]["chunk_strategy"] == "heading"


def _add_embeddings(path: Path) -> int:
    chunks = json.loads(path.read_text(encoding="utf-8"))
    for item in chunks:
        item["embedding"] = [0.0] * 1536
    path.write_text(json.dumps(chunks), encoding="utf-8")
    return len(chunks)


def _tag_file(path: Path) -> tuple[Path, int]:
    chunks = json.loads(path.read_text(encoding="utf-8"))
    for item in chunks:
        item.update({"tags": ["personal"], "mood": "curious", "topic_label": "random", "moment_type": "idea", "visual_context": None})
    path.write_text(json.dumps(chunks), encoding="utf-8")
    return path, len(chunks)
