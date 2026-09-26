"""Explicit, idempotent extraction of review-only actions from voice journals."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from scripts.transcribe import REPOSITORY_ROOT, load_environment_file
from shared.clients import create_supabase_client
from shared.journal_actions import action_key, canonical_journal_rows, journal_fingerprint


def prompt(chunks: list[dict[str, Any]]) -> str:
    source = "\n\n".join(f"[chunk {chunk['chunk_index']}] {chunk['content']}" for chunk in chunks)
    return f'''Extract only concrete actions the speaker explicitly commits to or clearly asks themselves to do.
Return JSON only: {{"actions":[{{"wording":string,"source_chunk_index":integer,"evidence":string}}]}}.
If there are no explicit actions, return {{"actions":[]}}. Do not infer plans, turn ideas into todos, or invent deadlines.
`evidence` must be a verbatim phrase from the cited chunk that supports the suggestion. Wording is an AI suggestion for human review, never an automatic task.

Journal:
{source}'''


async def openai_extract_actions(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for action extraction")
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=api_key, base_url=os.environ.get("OPENAI_BASE_URL") or None)
    response = await client.chat.completions.create(
        model=os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": prompt(chunks)}],
    )
    content = response.choices[0].message.content or ""
    payload = json.loads(content.removeprefix("```json").removesuffix("```").strip())
    return payload.get("actions", []) if isinstance(payload, dict) and isinstance(payload.get("actions"), list) else []


def valid_actions(raw_actions: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_index = {chunk.get("chunk_index"): chunk for chunk in chunks}
    valid: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_actions:
        if not isinstance(raw, dict):
            continue
        wording, evidence, index = raw.get("wording"), raw.get("evidence"), raw.get("source_chunk_index")
        chunk = by_index.get(index)
        if not isinstance(wording, str) or not wording.strip() or not isinstance(evidence, str) or not evidence.strip() or chunk is None:
            continue
        if " ".join(evidence.split()).lower() not in " ".join(str(chunk.get("content", "")).split()).lower():
            continue
        key = action_key(str(chunk.get("id", "")), wording)
        if key not in seen:
            valid.append({"source_entry_id": chunk["id"], "action_key": key, "wording": wording.strip(), "evidence": evidence.strip()})
            seen.add(key)
    return valid


async def extract_current_journals(
    *, client: Any, extractor: Callable[[list[dict[str, Any]]], Awaitable[list[dict[str, Any]]]] = openai_extract_actions,
    dry_run: bool = False,
) -> dict[str, int]:
    rows = (client.table("entries").select("id,content,source_file,chunk_index,chunk_strategy").eq("source_type", "voice_memo").order("source_file").order("chunk_index").execute().data or [])
    grouped: dict[str, list[dict[str, Any]]] = {}
    for chunk in canonical_journal_rows(rows):
        grouped.setdefault(chunk["source_file"], []).append(chunk)
    processed = suggestions = skipped = 0
    for source_file, chunks in grouped.items():
        fingerprint = journal_fingerprint(chunks)
        marker = client.table("journal_action_extractions").select("source_fingerprint").eq("source_file", source_file).execute().data or []
        if marker and marker[0].get("source_fingerprint") == fingerprint:
            skipped += 1
            continue
        candidates = valid_actions(await extractor(chunks), chunks)
        processed += 1
        suggestions += len(candidates)
        if dry_run:
            continue
        if candidates:
            now = datetime.now(timezone.utc).isoformat()
            rows_to_store = [{**candidate, "source_file": source_file, "extracted_at": now} for candidate in candidates]
            client.table("journal_action_items").upsert(rows_to_store, on_conflict="source_file,action_key").execute()
        client.table("journal_action_extractions").upsert({"source_file": source_file, "source_fingerprint": fingerprint, "extracted_at": datetime.now(timezone.utc).isoformat()}, on_conflict="source_file").execute()
    return {"journals_processed": processed, "suggestions_found": suggestions, "journals_skipped": skipped}


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract review-only action suggestions from ingested voice journals.")
    parser.add_argument("--dry-run", action="store_true", help="Call extraction but do not save suggestions or markers.")
    args = parser.parse_args()
    load_environment_file(REPOSITORY_ROOT / ".env")
    print(json.dumps(asyncio.run(extract_current_journals(client=create_supabase_client(), dry_run=args.dry_run))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
