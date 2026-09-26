from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import compare_chunking


def test_comparison_creates_both_strategies_and_marks_split_merge_disagreements(tmp_path: Path) -> None:
    transcript = tmp_path / "memo.json"
    transcript.write_text(json.dumps({"segments": [{"start": 0.0, "end": 1.0, "text": "Cats purr."}, {"start": 3.5, "end": 4.0, "text": "Cats nap."}], "words": []}), encoding="utf-8")
    result = compare_chunking.create_strategy_chunks([transcript], semantic_embedder=lambda _: [[1.0, 0.0], [0.9, 0.1]])
    report = compare_chunking.render_comparison(transcript, result[transcript])
    assert (tmp_path / "memo.pause.chunks.json").exists()
    assert (tmp_path / "memo.semantic.chunks.json").exists()
    assert [row["chunk_strategy"] for row in result[transcript]["pause"]] == ["pause", "pause"]
    assert [row["chunk_strategy"] for row in result[transcript]["semantic"]] == ["semantic"]
    assert "0:03" in report
    assert "split/merge disagreement" in report


def test_transcript_files_requires_three_to_five_sources(tmp_path: Path) -> None:
    for name in ("a.json", "b.json"):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    try:
        compare_chunking.transcript_files(tmp_path, 3)
    except ValueError as error:
        assert "3–5" in str(error)
    else:
        raise AssertionError("Expected source-count validation")


def test_transcribe_audio_files_transcribes_each_selected_audio_once(monkeypatch: Any, tmp_path: Path) -> None:
    audio = [tmp_path / f"memo-{index}.m4a" for index in range(3)]
    for path in audio:
        path.write_bytes(b"audio")
    monkeypatch.setattr(compare_chunking.transcribe, "input_files", lambda folder: audio)
    monkeypatch.setattr(compare_chunking, "_required", lambda name, operation: "token")
    calls: list[Path] = []
    monkeypatch.setattr(compare_chunking.transcribe, "transcribe_file", lambda path, token: calls.append(path) or path.with_suffix(".json"))
    assert compare_chunking.transcribe_audio_files(tmp_path, 3) == [path.with_suffix(".json") for path in audio]
    assert calls == audio


def test_render_comparison_preserves_a_hundred_character_preview(tmp_path: Path) -> None:
    transcript = tmp_path / "memo.json"
    content = "word " * 30
    report = compare_chunking.render_comparison(transcript, {"pause": [{"content": content, "audio_offset": 0.0, "chunk_index": 0}], "semantic": []})
    assert "#0:" in report
    assert ("word " * 20).strip() in report
    assert "split/merge disagreement" in report


def test_enrich_and_store_writes_each_strategy_with_its_own_identity(monkeypatch: Any, tmp_path: Path) -> None:
    source = tmp_path / "memo.json"
    rows = {source: {"pause": [_row(source, "pause")], "semantic": [_row(source, "semantic")]}}
    stored: list[str] = []
    monkeypatch.setattr(compare_chunking.embed, "enrich_chunks", lambda chunks: 0)
    async def fake_tag(chunks: list[dict[str, Any]]) -> None: pass
    monkeypatch.setattr(compare_chunking.tag, "enrich_chunks", fake_tag)
    monkeypatch.setattr(compare_chunking.store, "store_chunks", lambda chunks, client: stored.append(chunks[0]["chunk_strategy"]) or len(chunks))
    assert compare_chunking.enrich_and_store(rows, client=object()) == 2
    assert stored == ["pause", "semantic"]
    assert (tmp_path / "memo.pause.chunks.json").exists()
    assert (tmp_path / "memo.semantic.chunks.json").exists()


def test_store_only_skips_remote_enrichment(monkeypatch: Any, tmp_path: Path) -> None:
    source = tmp_path / "memo.json"
    rows = {source: {"pause": [_row(source, "pause")], "semantic": [_row(source, "semantic")]}}
    monkeypatch.setattr(compare_chunking.embed, "enrich_chunks", lambda chunks: (_ for _ in ()).throw(AssertionError("should not embed")))
    monkeypatch.setattr(compare_chunking.store, "store_chunks", lambda chunks, client: len(chunks))
    assert compare_chunking.enrich_and_store(rows, client=object(), enrich=False) == 2


def _row(source: Path, strategy: str) -> dict[str, Any]:
    return {"content": "remember this", "source_file": str(source), "audio_offset": 0.0, "chunk_index": 0, "chunk_strategy": strategy}
