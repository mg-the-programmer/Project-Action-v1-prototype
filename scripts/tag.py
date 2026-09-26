"""Classify chunks with the configured OpenAI-compatible chat model."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Awaitable, Callable

from scripts.transcribe import REPOSITORY_ROOT, load_environment_file

SEED_TAGS = ("youtube-idea", "instagram-idea", "business", "cybersecurity", "genai", "personal", "shower-thought", "daily-journal", "content-script", "example", "personal-scenario")
MOODS = ("excited", "happy", "reflective", "frustrated", "curious", "neutral")
TOPICS = ("content-creation", "cybersecurity", "ai-ml", "personal-growth", "business-ideas", "random")
CONCURRENCY = 5
TAGGING_FIELDS = ("tags", "mood", "topic_label", "moment_type", "visual_context")


def prompt(content: str) -> str:
    return f'''Classify this personal knowledge-base chunk. Return only one JSON object with exactly these keys:
{{"tags": [string], "suggested_tags": [string], "mood": string, "topic_label": string, "moment_type": string|null, "visual_context": string|null}}

Rules:
- tags may contain only values from this seed taxonomy: {list(SEED_TAGS)}.
- Put a useful tag that is not in the seed taxonomy only in suggested_tags, never in tags.
- mood must be one of: {list(MOODS)}.
- topic_label must be one of: {list(TOPICS)}.
- moment_type must be one of: happy_moment, idea, reflection, or null.
- visual_context must be a short, concrete scene description only when moment_type is happy_moment; otherwise it must be null.

Chunk:
{content}'''


def normalize_tagging(raw: dict[str, Any]) -> dict[str, Any]:
    raw_tags = _string_list(raw.get("tags"))
    tags = _unique(tag for tag in raw_tags if tag in SEED_TAGS)
    # A model occasionally puts a proposed tag in ``tags`` despite the schema.
    # Preserve it for review rather than allowing an uncontrolled stored tag.
    suggestions = _unique(
        tag for tag in [*_string_list(raw.get("suggested_tags")), *raw_tags] if tag not in SEED_TAGS
    )
    mood = raw.get("mood") if raw.get("mood") in MOODS else "neutral"
    topic = raw.get("topic_label") if raw.get("topic_label") in TOPICS else "random"
    moment = raw.get("moment_type") if raw.get("moment_type") in {"happy_moment", "idea", "reflection"} else None
    visual_context = raw.get("visual_context") if moment == "happy_moment" else None
    return {
        "tags": tags,
        "mood": mood,
        "topic_label": topic,
        "moment_type": moment,
        "visual_context": str(visual_context).strip() or None if visual_context is not None else None,
        "suggested_tags": suggestions,
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _unique(values: Any) -> list[str]:
    return list(dict.fromkeys(values))


async def openai_tag(content: str) -> dict[str, Any]:
    """Return taxonomy metadata using the configured OpenAI-compatible client."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for tagging")
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key, base_url=os.environ.get("OPENAI_BASE_URL") or None)
    response = await client.chat.completions.create(
        model=os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": prompt(content)}],
    )
    text = response.choices[0].message.content or ""
    return normalize_tagging(json.loads(text.removeprefix("```json").removesuffix("```").strip()))


async def enrich_chunks(
    chunks: list[dict[str, Any]], tagger: Callable[[str], Awaitable[dict[str, Any]]] = openai_tag
) -> int:
    pending = [chunk for chunk in chunks if not all(field in chunk for field in TAGGING_FIELDS)]
    semaphore = asyncio.Semaphore(CONCURRENCY)
    async def tag_chunk(chunk: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        async with semaphore:
            return chunk, normalize_tagging(await tagger(str(chunk["content"])))
    for chunk, metadata in await asyncio.gather(*(tag_chunk(chunk) for chunk in pending)):
        suggestions = metadata.pop("suggested_tags")
        chunk.update(metadata)
        if suggestions:
            chunk["suggested_tags"] = suggestions
    return len(pending)


async def tag_file(
    path: Path, tagger: Callable[[str], Awaitable[dict[str, Any]]] = openai_tag
) -> tuple[Path, int]:
    chunks = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(chunks, list):
        raise ValueError(f"Chunk file must contain an array: {path}")
    count = await enrich_chunks(chunks, tagger)
    suggestions = sorted({tag for chunk in chunks for tag in chunk.get("suggested_tags", []) if tag not in SEED_TAGS})
    if suggestions:
        # Keep this review queue useful on safe reruns: do not append the same
        # proposal on every idempotent pipeline execution.
        log_path = path.parent / "new_tags.log"
        existing = set(log_path.read_text(encoding="utf-8").splitlines()) if log_path.exists() else set()
        new_suggestions = [item for item in suggestions if item not in existing]
        if new_suggestions:
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write("\n".join(new_suggestions) + "\n")
    path.write_text(json.dumps(chunks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path, count


def main() -> int:
    parser = argparse.ArgumentParser(description="Tag an embedded chunk JSON file.")
    parser.add_argument("chunks", type=Path)
    args = parser.parse_args()
    load_environment_file(REPOSITORY_ROOT / ".env")
    path, count = asyncio.run(tag_file(args.chunks))
    print(f"Tagged {count} chunks in {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
