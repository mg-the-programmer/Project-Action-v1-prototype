from __future__ import annotations

import json
from pathlib import Path

from scripts import chunk


def test_chunk_transcript_file_splits_pause_and_writes_chunking_contract(tmp_path: Path) -> None:
    transcript = tmp_path / "memo.json"
    transcript.write_text(
        json.dumps(
            {
                "text": "First thought. Second thought. Final thought.",
                "segments": [
                    {"start": 0.0, "end": 1.0, "text": "First thought."},
                    {"start": 1.3, "end": 2.0, "text": "Second thought."},
                    {"start": 4.2, "end": 5.0, "text": "Final thought."},
                ],
                "words": [
                    {"word": "First", "start": 0.0, "end": 0.4},
                    {"word": "thought.", "start": 0.5, "end": 1.0},
                    {"word": "Second", "start": 1.3, "end": 1.6},
                    {"word": "thought.", "start": 1.7, "end": 2.0},
                    {"word": "Final", "start": 4.2, "end": 4.5},
                    {"word": "thought.", "start": 4.6, "end": 5.0},
                ],
            }
        ),
        encoding="utf-8",
    )

    output = chunk.chunk_transcript_file(transcript, strategy="pause")

    assert output == tmp_path / "memo.pause.chunks.json"
    assert json.loads(output.read_text(encoding="utf-8")) == [
        {
            "content": "First thought. Second thought.",
            "source_type": "voice_memo",
            "source_file": str(transcript),
            "audio_offset": 0.0,
            "word_timestamps": [
                {"word": "First", "start": 0.0, "end": 0.4},
                {"word": "thought.", "start": 0.5, "end": 1.0},
                {"word": "Second", "start": 1.3, "end": 1.6},
                {"word": "thought.", "start": 1.7, "end": 2.0},
            ],
            "chunk_index": 0,
            "chunk_strategy": "pause",
        },
        {
            "content": "Final thought.",
            "source_type": "voice_memo",
            "source_file": str(transcript),
            "audio_offset": 4.2,
            "word_timestamps": [
                {"word": "Final", "start": 4.2, "end": 4.5},
                {"word": "thought.", "start": 4.6, "end": 5.0},
            ],
            "chunk_index": 1,
            "chunk_strategy": "pause",
        },
    ]


def test_chunk_transcript_file_splits_at_semantic_similarity_drop(tmp_path: Path) -> None:
    transcript = tmp_path / "memo.json"
    transcript.write_text(
        json.dumps(
            {
                "segments": [
                    {"start": 0.0, "end": 1.0, "text": "Cats purr."},
                    {"start": 1.1, "end": 2.0, "text": "Cats nap."},
                    {"start": 2.1, "end": 3.0, "text": "Markets fluctuate."},
                ],
                "words": [],
            }
        ),
        encoding="utf-8",
    )

    output = chunk.chunk_transcript_file(
        transcript,
        strategy="semantic",
        embedder=lambda sentences: [[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]],
    )

    chunks = json.loads(output.read_text(encoding="utf-8"))
    assert [item["content"] for item in chunks] == ["Cats purr. Cats nap.", "Markets fluctuate."]
    assert [item["audio_offset"] for item in chunks] == [0.0, 2.1]
    assert all(item["chunk_strategy"] == "semantic" for item in chunks)


def test_chunk_markdown_file_splits_headings_and_long_sections_at_paragraphs(tmp_path: Path) -> None:
    note = tmp_path / "ideas.md"
    first_paragraph = "one " * 250
    second_paragraph = "two " * 250
    note.write_text(
        f"# Title\n\n## Idea\n{first_paragraph}\n\n{second_paragraph}\n\n### Detail\nKeep this.",
        encoding="utf-8",
    )

    output = chunk.chunk_markdown_file(note)

    chunks = json.loads(output.read_text(encoding="utf-8"))
    assert [item["content"] for item in chunks] == [
        "# Title\n\n## Idea\n" + first_paragraph.strip(),
        second_paragraph.strip(),
        "### Detail\nKeep this.",
    ]
    assert [item["chunk_index"] for item in chunks] == [0, 1, 2]
    assert all(item["source_type"] == "notion_note" for item in chunks)
    assert all(item["audio_offset"] is None and item["word_timestamps"] is None for item in chunks)
    assert all(item["chunk_strategy"] == "heading" for item in chunks)


def test_chunk_markdown_file_splits_an_oversized_single_paragraph(tmp_path: Path) -> None:
    note = tmp_path / "long.md"
    note.write_text("## Long\n" + "word " * 850, encoding="utf-8")

    output = chunk.chunk_markdown_file(note)

    chunks = json.loads(output.read_text(encoding="utf-8"))
    assert len(chunks) == 3
    assert all(len(item["content"].split()) <= 400 for item in chunks)
    assert " ".join(item["content"] for item in chunks).split() == ("## Long\n" + "word " * 850).split()


def test_input_files_accepts_transcript_and_markdown_folders_but_ignores_chunk_outputs(tmp_path: Path) -> None:
    (tmp_path / "memo.json").write_text("{}", encoding="utf-8")
    (tmp_path / "note.md").write_text("# Note", encoding="utf-8")
    (tmp_path / "memo.pause.chunks.json").write_text("[]", encoding="utf-8")

    assert chunk.input_files(tmp_path) == [tmp_path / "memo.json", tmp_path / "note.md"]
