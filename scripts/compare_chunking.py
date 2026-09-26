"""Compare pause and semantic chunking for the same voice-memo transcripts.

Usage:
    python scripts/compare_chunking.py datasets/voice_journals --limit 3 --dry-run
    python scripts/compare_chunking.py raw/audio --limit 3

The default mode creates, enriches, and upserts chunks for both strategies. Use
``--dry-run`` to print the comparison without calling tagging or Supabase.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

# Allow the documented ``python scripts/compare_chunking.py`` invocation.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import chunk, embed, store, tag, transcribe
from scripts.transcribe import REPOSITORY_ROOT, load_environment_file

STRATEGIES = ("pause", "semantic")
SemanticEmbedder = Callable[[list[str]], list[list[float]]]


def transcript_files(folder: Path, limit: int) -> list[Path]:
    """Select three to five source transcript files, excluding generated chunks."""
    selected = [path for path in chunk.input_files(folder) if path.suffix.lower() == ".json"][:limit]
    if not 3 <= len(selected) <= 5:
        raise ValueError(f"Expected 3–5 transcript JSON files; found {len(selected)} in {folder}")
    return selected


def transcribe_audio_files(folder: Path, limit: int) -> list[Path]:
    """Transcribe three to five audio inputs once before comparing both strategies."""
    files = transcribe.input_files(folder)[:limit]
    if not 3 <= len(files) <= 5:
        raise ValueError(f"Expected 3–5 audio files; found {len(files)} in {folder}")
    token = _required("HCAPTCHA_TOKEN", "audio transcription")
    return [transcribe.transcribe_file(audio, token) or audio.with_suffix(".json") for audio in files]


def create_strategy_chunks(transcripts: list[Path], *, semantic_embedder: SemanticEmbedder | None = None) -> dict[Path, dict[str, list[dict[str, Any]]]]:
    """Create both chunk outputs for every source and return their parsed rows."""
    results: dict[Path, dict[str, list[dict[str, Any]]]] = {}
    for transcript in transcripts:
        outputs = {
            "pause": chunk.chunk_transcript_file(transcript, strategy="pause"),
            "semantic": chunk.chunk_transcript_file(transcript, strategy="semantic", embedder=semantic_embedder),
        }
        results[transcript] = {strategy: _read_chunks(output) for strategy, output in outputs.items()}
    return results


def comparison_rows(chunks_by_strategy: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Align starts so split/merge disagreements are explicit in the report."""
    pause, semantic = chunks_by_strategy["pause"], chunks_by_strategy["semantic"]
    starts = sorted({float(item["audio_offset"]) for item in pause + semantic})
    return [{"start": start, "pause": _chunk_at_start(pause, start), "semantic": _chunk_at_start(semantic, start)} for start in starts]


def render_comparison(transcript: Path, chunks_by_strategy: dict[str, list[dict[str, Any]]]) -> str:
    """Render chunk number, start, and first 100 content characters side-by-side."""
    heading = "start     | pause (chunk, first 100 characters)" + " " * 66 + "| semantic (chunk, first 100 characters)"
    lines = [f"\n{transcript.name}", heading, "-" * len(heading)]
    for row in comparison_rows(chunks_by_strategy):
        marker = "  <-- split/merge disagreement" if bool(row["pause"]) != bool(row["semantic"]) else ""
        lines.append(f"{_format_timestamp(row['start']):9} | {_display_chunk(row['pause']):108} | {_display_chunk(row['semantic']):108}{marker}")
    return "\n".join(lines)


def enrich_and_store(
    chunks_by_file: dict[Path, dict[str, list[dict[str, Any]]]], client: Any | None = None, *, enrich: bool = True
) -> int:
    """Optionally enrich, then upsert each strategy with independent identities."""
    all_chunks = [strategies[strategy] for strategies in chunks_by_file.values() for strategy in STRATEGIES]
    if enrich:
        for chunks in all_chunks:
            embed.enrich_chunks(chunks)
        asyncio.run(_tag_all(all_chunks))
    total = sum(store.store_chunks(chunks, client) for chunks in all_chunks)
    for chunks in all_chunks:
        _write_chunks_for_strategy(chunks)
    return total


async def _tag_all(all_chunks: list[list[dict[str, Any]]]) -> None:
    """Use one event loop for all files, avoiding cross-loop HTTP client cleanup."""
    for chunks in all_chunks:
        await tag.enrich_chunks(chunks)


def _chunk_at_start(chunks: list[dict[str, Any]], start: float) -> dict[str, Any] | None:
    return next((item for item in chunks if float(item["audio_offset"]) == start), None)


def _display_chunk(item: dict[str, Any] | None) -> str:
    if item is None:
        return "—"
    return f"#{item['chunk_index']}: {' '.join(item['content'].split())[:100]}"


def _format_timestamp(seconds: float) -> str:
    minutes, remainder = divmod(int(seconds), 60)
    return f"{minutes}:{remainder:02d}"


def _read_chunks(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def _required(name: str, operation: str) -> str:
    import os
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required for {operation}")
    return value


def _write_chunks_for_strategy(chunks: list[dict[str, Any]]) -> None:
    if chunks:
        source, strategy = Path(chunks[0]["source_file"]), chunks[0]["chunk_strategy"]
        chunk.write_chunks(source.with_name(f"{source.stem}.{strategy}{chunk.CHUNK_OUTPUT_SUFFIX}"), chunks)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare pause and semantic chunking for three to five voice memos.")
    parser.add_argument("folder", type=Path, help="Folder containing transcript JSON files")
    parser.add_argument("--limit", type=int, default=3, help="Number of source transcripts to compare (3–5)")
    parser.add_argument("--dry-run", action="store_true", help="Skip embedding, tagging, and database upserts")
    parser.add_argument("--store-only", action="store_true", help="Upsert strategy chunks without remote embedding or tagging")
    parser.add_argument("--transcribe", action="store_true", help="Transcribe 3–5 audio files once before comparing their outputs")
    args = parser.parse_args()
    # Transcript text may include emoji or non-Latin scripts on Windows consoles.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not 3 <= args.limit <= 5:
        parser.error("--limit must be between 3 and 5")
    load_environment_file(REPOSITORY_ROOT / ".env")
    try:
        sources = transcribe_audio_files(args.folder, args.limit) if args.transcribe else transcript_files(args.folder, args.limit)
        results = create_strategy_chunks(sources)
        for transcript, strategies in results.items():
            print(render_comparison(transcript, strategies))
        if args.dry_run:
            print("\nDry run: wrote both chunk outputs; skipped embedding, tagging, and storage.")
        else:
            mode = "without enrichment" if args.store_only else "after embedding and tagging"
            print(f"\nUpserted {enrich_and_store(results, enrich=not args.store_only)} entries across both strategies ({mode}).")
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
