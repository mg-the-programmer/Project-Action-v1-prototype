"""Create embedding-ready chunks from transcript JSON and Notion Markdown.

Usage:
    python scripts/chunk.py raw/audio --strategy pause
    python scripts/chunk.py raw/audio --strategy semantic
    python scripts/chunk.py raw/notes
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from scripts.transcribe import REPOSITORY_ROOT, load_environment_file
from shared.clients import embed_texts

CHUNK_OUTPUT_SUFFIX = ".chunks.json"
MARKDOWN_EXTENSIONS = {".md", ".markdown"}
PAUSE_GAP_SECONDS = 2.0
SEMANTIC_SIMILARITY_THRESHOLD = 0.75
MAX_SECTION_WORDS = 400
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
HEADING_BOUNDARY = re.compile(r"(?=^#{2,3}\s)", re.MULTILINE)

EmbeddingProvider = Callable[[list[str]], list[list[float]]]


def input_files(input_path: Path) -> list[Path]:
    """Return transcript JSON and Markdown files from a file or top-level folder."""
    if not input_path.exists():
        raise ValueError(f"Input path does not exist: {input_path}")
    candidates: Iterable[Path] = [input_path] if input_path.is_file() else input_path.iterdir()
    files = [
        path
        for path in candidates
        if path.is_file()
        and path.suffix.lower() in {".json", *MARKDOWN_EXTENSIONS}
        and not path.name.endswith(CHUNK_OUTPUT_SUFFIX)
    ]
    if input_path.is_file() and not files:
        raise ValueError(f"Unsupported input format: {input_path.suffix or '(no extension)'}")
    return sorted(files, key=lambda path: path.name.lower())


def chunk_transcript_file(
    transcript_path: Path,
    strategy: str,
    embedder: EmbeddingProvider | None = None,
    similarity_threshold: float = SEMANTIC_SIMILARITY_THRESHOLD,
) -> Path:
    """Write chunks for one transcript, preserving its timestamps and selected strategy."""
    data = json.loads(transcript_path.read_text(encoding="utf-8"))
    segments = data.get("segments", [])
    words = data.get("words", [])
    if not isinstance(segments, list) or not isinstance(words, list):
        raise ValueError(f"Transcript must contain list-valued segments and words: {transcript_path}")
    if strategy == "pause":
        groups = _pause_groups(segments)
    elif strategy == "semantic":
        if embedder is None:
            embedder = openai_embedder()
        groups = _semantic_groups(segments, embedder, similarity_threshold)
    else:
        raise ValueError(f"Unsupported audio strategy: {strategy}")
    chunks = _audio_chunks(groups, words, transcript_path, strategy)
    output = transcript_path.with_name(f"{transcript_path.stem}.{strategy}{CHUNK_OUTPUT_SUFFIX}")
    write_chunks(output, chunks)
    return output


def chunk_markdown_file(markdown_path: Path) -> Path:
    """Write heading- and paragraph-based chunks for one Notion Markdown export."""
    text = markdown_path.read_text(encoding="utf-8").strip()
    sections = [section.strip() for section in HEADING_BOUNDARY.split(text) if section.strip()]
    if len(sections) > 1 and not re.match(r"^#{2,3}\s", sections[0]):
        sections[1] = f"{sections[0]}\n\n{sections[1]}"
        sections.pop(0)
    contents = [part for section in sections for part in _split_long_section(section)]
    chunks = [
        {
            "content": content,
            "source_type": "notion_note",
            "source_file": str(markdown_path),
            "audio_offset": None,
            "word_timestamps": None,
            "chunk_index": index,
            "chunk_strategy": "heading",
        }
        for index, content in enumerate(contents)
    ]
    output = markdown_path.with_name(f"{markdown_path.stem}{CHUNK_OUTPUT_SUFFIX}")
    write_chunks(output, chunks)
    return output


def _pause_groups(segments: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups: list[list[dict[str, Any]]] = []
    for segment in segments:
        if not _valid_timed_text(segment):
            continue
        if groups and float(segment["start"]) - float(groups[-1][-1]["end"]) > PAUSE_GAP_SECONDS:
            groups.append([])
        if not groups:
            groups.append([])
        groups[-1].append(segment)
    return groups


def _semantic_groups(
    segments: list[dict[str, Any]], embedder: EmbeddingProvider, threshold: float
) -> list[list[dict[str, Any]]]:
    sentences = _sentences_from_segments(segments)
    if not sentences:
        return []
    vectors = embedder([sentence["text"] for sentence in sentences])
    if len(vectors) != len(sentences):
        raise ValueError("Embedding provider returned a different number of vectors than input sentences")
    groups: list[list[dict[str, Any]]] = [[sentences[0]]]
    for sentence, previous, current in zip(sentences[1:], vectors, vectors[1:]):
        if _cosine_similarity(previous, current) < threshold:
            groups.append([])
        groups[-1].append(sentence)
    return groups


def _sentences_from_segments(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sentences: list[dict[str, Any]] = []
    for segment in segments:
        if not _valid_timed_text(segment):
            continue
        pieces = [piece.strip() for piece in SENTENCE_BOUNDARY.split(segment["text"].strip()) if piece.strip()]
        duration = float(segment["end"]) - float(segment["start"])
        total_characters = sum(len(piece) for piece in pieces) or 1
        cursor = float(segment["start"])
        for index, piece in enumerate(pieces):
            end = float(segment["end"]) if index == len(pieces) - 1 else cursor + duration * len(piece) / total_characters
            sentences.append({"start": cursor, "end": end, "text": piece})
            cursor = end
    return sentences


def _audio_chunks(
    groups: list[list[dict[str, Any]]], words: list[dict[str, Any]], source: Path, strategy: str
) -> list[dict[str, Any]]:
    chunks = []
    for index, group in enumerate(groups):
        start, end = float(group[0]["start"]), float(group[-1]["end"])
        chunks.append(
            {
                "content": " ".join(segment["text"].strip() for segment in group),
                "source_type": "voice_memo",
                "source_file": str(source),
                "audio_offset": start,
                "word_timestamps": [word for word in words if _word_overlaps(word, start, end)],
                "chunk_index": index,
                "chunk_strategy": strategy,
            }
        )
    return chunks


def _split_long_section(section: str) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", section) if paragraph.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    for paragraph in paragraphs:
        paragraph_words = len(paragraph.split())
        if paragraph_words > MAX_SECTION_WORDS:
            if current:
                chunks.append("\n\n".join(current))
                current, current_words = [], 0
            chunks.extend(_split_oversized_paragraph(paragraph))
            continue
        if current and current_words + paragraph_words > MAX_SECTION_WORDS:
            chunks.append("\n\n".join(current))
            current, current_words = [], 0
        current.append(paragraph)
        current_words += paragraph_words
    if current:
        chunks.append("\n\n".join(current))
    return chunks


def _split_oversized_paragraph(paragraph: str) -> list[str]:
    """Keep the size target when no paragraph boundary exists to use instead."""
    words = paragraph.split()
    return [" ".join(words[start : start + MAX_SECTION_WORDS]) for start in range(0, len(words), MAX_SECTION_WORDS)]


def _valid_timed_text(item: dict[str, Any]) -> bool:
    return bool(item.get("text", "").strip()) and "start" in item and "end" in item


def _word_overlaps(word: dict[str, Any], start: float, end: float) -> bool:
    return "start" in word and "end" in word and float(word["end"]) >= start and float(word["start"]) <= end


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    return sum(a * b for a, b in zip(left, right)) / denominator if denominator else 0.0


def openai_embedder() -> EmbeddingProvider:
    """Return the configured OpenAI embedding boundary, imported only for semantic CLI runs."""
    return embed_texts


def write_chunks(path: Path, chunks: list[dict[str, Any]]) -> None:
    """Persist chunk rows using the shared chunk-file representation."""
    path.write_text(json.dumps(chunks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Chunk transcript JSON or Notion Markdown into embedding-ready JSON.")
    parser.add_argument("input", type=Path, help="A transcript/Markdown file or a folder containing them")
    parser.add_argument("--strategy", choices=("pause", "semantic"), default="pause", help="Audio chunking strategy")
    arguments = parser.parse_args()
    load_environment_file(REPOSITORY_ROOT / ".env")
    try:
        files = input_files(arguments.input)
        if not files:
            print(f"No transcript JSON or Markdown files found in {arguments.input}")
            return 0
        for path in files:
            output = chunk_markdown_file(path) if path.suffix.lower() in MARKDOWN_EXTENSIONS else chunk_transcript_file(path, arguments.strategy)
            print(f"Wrote {output}")
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
