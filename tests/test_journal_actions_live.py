"""Optional cloud persistence coverage for the journal-action migration."""
from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest

from scripts.extract_actions import extract_current_journals
from scripts.transcribe import REPOSITORY_ROOT, load_environment_file
from shared.clients import create_supabase_client


@pytest.mark.integration
def test_journal_action_extraction_persists_and_cleans_up_on_supabase() -> None:
    load_environment_file(REPOSITORY_ROOT / ".env")
    if not all(os.environ.get(name) for name in ("SUPABASE_URL", "SUPABASE_KEY")):
        pytest.skip("configured Supabase is required")
    database = create_supabase_client()
    source_file = f"journal-action-live-{uuid4()}.json"
    entry_id: str | None = None
    try:
        created = database.table("entries").insert({
            "content": "I will email the editor about the outline tomorrow.", "source_type": "voice_memo",
            "source_file": source_file, "chunk_index": 0, "chunk_strategy": "pause",
            "recorded_at": "2026-09-26T12:00:00Z",
        }).execute().data or []
        entry_id = created[0]["id"]
        async def extractor(_: list[dict[str, object]]) -> list[dict[str, object]]:
            return [{"wording": "Email the editor", "source_chunk_index": 0, "evidence": "email the editor about the outline tomorrow"}]
        result = asyncio.run(extract_current_journals(client=database, extractor=extractor, source_files={source_file}))
        assert result == {"journals_processed": 1, "suggestions_found": 1, "journals_skipped": 0}
        actions = database.table("journal_action_items").select("source_entry_id,status").eq("source_file", source_file).execute().data or []
        assert actions == [{"source_entry_id": entry_id, "status": "suggested"}]
        assert asyncio.run(extract_current_journals(client=database, extractor=extractor, source_files={source_file}))["journals_skipped"] == 1
    finally:
        database.table("journal_action_items").delete().eq("source_file", source_file).execute()
        database.table("journal_action_extractions").delete().eq("source_file", source_file).execute()
        if entry_id:
            database.table("entries").delete().eq("id", entry_id).execute()
