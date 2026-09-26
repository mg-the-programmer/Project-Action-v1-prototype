"""Run the complete personal knowledge-base ingestion pipeline for one folder."""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

from scripts import chunk, embed, store, tag, transcribe


def ingest_audio(folder: Path, *, client: Any | None = None) -> dict[str, int]:
    """Transcribe, pause-chunk, embed, tag, and store every audio file in a folder."""
    files = transcribe.input_files(folder)
    hcaptcha_token = _required("HCAPTCHA_TOKEN", "audio transcription")
    chunk_paths: list[Path] = []
    for audio in files:
        transcript = transcribe.transcribe_file(audio, hcaptcha_token) or audio.with_suffix(".json")
        chunk_paths.append(chunk.chunk_transcript_file(transcript, strategy="pause"))
    return _enrich_and_store(chunk_paths, len(files), client)


def ingest_notes(folder: Path, *, client: Any | None = None) -> dict[str, int]:
    """Heading-chunk, embed, tag, and store every Notion Markdown export in a folder."""
    files = [path for path in chunk.input_files(folder) if path.suffix.lower() in chunk.MARKDOWN_EXTENSIONS]
    chunk_paths = [chunk.chunk_markdown_file(path) for path in files]
    return _enrich_and_store(chunk_paths, len(files), client)


def _enrich_and_store(chunk_paths: list[Path], files_processed: int, client: Any | None) -> dict[str, int]:
    chunks_created = embedded = tagged = entries_upserted = 0
    for path in chunk_paths:
        chunks_created += len(_read_chunks(path))
        embedded += embed.embed_file(path)[1]
        tagged += asyncio.run(tag.tag_file(path))[1]
        entries_upserted += store.store_file(path, client)[1]
    return {
        "files_processed": files_processed,
        "chunks_created": chunks_created,
        "chunks_embedded": embedded,
        "chunks_tagged": tagged,
        "entries_upserted": entries_upserted,
    }


def _read_chunks(path: Path) -> list[dict[str, Any]]:
    import json
    return json.loads(path.read_text(encoding="utf-8"))


def _required(name: str, operation: str) -> str:
    import os
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required for {operation}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest an audio or Notion Markdown folder into Supabase.")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--type", required=True, choices=("audio", "notes"), dest="source_type")
    args = parser.parse_args()
    transcribe.load_environment_file(transcribe.REPOSITORY_ROOT / ".env")
    try:
        summary = ingest_audio(args.folder) if args.source_type == "audio" else ingest_notes(args.folder)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    print("Files processed: {files_processed}; chunks created: {chunks_created}; entries upserted: {entries_upserted}".format(**summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
