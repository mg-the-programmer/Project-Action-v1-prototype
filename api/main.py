"""FastAPI endpoints for the local dashboard and phone integrations."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from mcp_server import server as knowledge_base
from scripts.extract_actions import extract_current_journals
from scripts.transcribe import load_environment_file
from shared.clients import create_supabase_client
from shared.journal_actions import get_journal_context, list_action_items, list_journals, review_action_item

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RETRIEVAL_LOG_FIELDS = "id,query,results,rating,comment,created_at"

load_environment_file(REPOSITORY_ROOT / ".env")

app = FastAPI(title="Personal Knowledge Base API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=15, ge=1)
    weight: float = Field(default=0.7, ge=0, le=1)


class IngestRequest(BaseModel):
    text: str = Field(min_length=1)
    source_type: Literal["voice_memo", "notion_note"]
    recorded_at: datetime | None = None


class TriggerWordRequest(BaseModel):
    word: str = Field(min_length=1)


class ActionReviewRequest(BaseModel):
    status: Literal["approved", "dismissed"]


class ActionExtractionRequest(BaseModel):
    dry_run: bool = False


def _domain_call(call: Any, *args: Any, **kwargs: Any) -> Any:
    """Translate known input errors from the shared application boundary."""
    try:
        return call(*args, **kwargs)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/search")
def search(request: SearchRequest) -> dict[str, Any]:
    """Return logged hybrid retrieval results through the shared search layer."""
    return _domain_call(knowledge_base.search_entries, request.query, request.top_k, request.weight)


@app.get("/entries")
def list_entries(
    tag: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    source_type: Literal["voice_memo", "notion_note"] | None = None,
) -> list[dict[str, Any]]:
    """List entries using any combination of the dashboard's supported filters."""
    return _domain_call(
        knowledge_base.list_entries,
        tag=tag,
        start=start.isoformat() if start else None,
        end=end.isoformat() if end else None,
        source_type=source_type,
    )


@app.get("/entries/{entry_id}/context")
def entry_context(entry_id: str) -> list[dict[str, Any]]:
    """Return the target entry and adjacent chunks from the same source."""
    return _domain_call(knowledge_base.get_entry_context, entry_id)


@app.get("/entries/{entry_id}/audio")
def entry_audio(entry_id: str) -> FileResponse:
    """Serve the local voice-memo source so a dashboard timestamp can seek it."""
    context = _domain_call(knowledge_base.get_entry_context, entry_id)
    entry = next((item for item in context if item.get("id") == entry_id), None)
    source_file = entry.get("source_file") if isinstance(entry, dict) else None
    if not isinstance(source_file, str) or not source_file:
        raise HTTPException(status_code=404, detail="No source file exists for the supplied entry")
    source_path = _resolve_audio_source(source_file)
    if source_path is None:
        raise HTTPException(status_code=404, detail="The source audio file is unavailable")
    return FileResponse(source_path)


def _resolve_audio_source(source_file: str) -> Path | None:
    """Find an original memo beside its transcript without allowing path escape."""
    transcript_path = (REPOSITORY_ROOT / source_file).resolve()
    if REPOSITORY_ROOT not in transcript_path.parents:
        return None
    original_path = Path(str(transcript_path).removesuffix(".json"))
    candidates = [
        original_path,
        *(path for path in original_path.parent.glob(f"{original_path.name}.*") if path.suffix.lower() in {".m4a", ".mp3", ".mp4", ".wav", ".webm"}),
    ]
    return next((path for path in candidates if path.is_file()), None)


@app.post("/ingest")
def ingest(request: IngestRequest) -> dict[str, Any]:
    """Embed, tag, and store one direct journal or note entry."""
    recorded_at = request.recorded_at.isoformat() if request.recorded_at else None
    return _domain_call(knowledge_base.ingest_entry, request.text, request.source_type, recorded_at)


@app.get("/journals")
def journals() -> list[dict[str, Any]]:
    """Inventory ingested voice journals without exposing duplicate strategies."""
    return list_journals(client=create_supabase_client())


@app.get("/journals/context")
def journal_context(source_file: str = Query(min_length=1)) -> list[dict[str, Any]]:
    """Return the canonical chunk context for one voice journal."""
    return _domain_call(get_journal_context, source_file, client=create_supabase_client())


@app.get("/journal-actions")
def journal_actions(status: Literal["suggested", "approved", "dismissed"] | None = None) -> list[dict[str, Any]]:
    """List local-only action suggestions and their source evidence."""
    return _domain_call(list_action_items, status, client=create_supabase_client())


@app.post("/journal-actions/{action_id}/review")
def review_journal_action(action_id: str, request: ActionReviewRequest) -> dict[str, Any]:
    """Record a human review decision; this never creates an external task."""
    return _domain_call(review_action_item, action_id, request.status, client=create_supabase_client())


@app.post("/journal-actions/extract")
def extract_journal_actions(request: ActionExtractionRequest) -> dict[str, int]:
    """Run the explicit OpenAI-compatible backfill for current voice journals."""
    import asyncio
    return asyncio.run(extract_current_journals(client=create_supabase_client(), dry_run=request.dry_run))


@app.get("/trigger-words")
def trigger_words() -> list[dict[str, Any]]:
    """List exact-match boost terms, newest first."""
    return knowledge_base.list_trigger_words()


@app.post("/trigger-words")
def add_trigger_word(request: TriggerWordRequest) -> dict[str, Any]:
    """Add an exact-match boost term, treating existing terms as successful."""
    return _domain_call(knowledge_base.add_trigger_word, request.word)


@app.delete("/trigger-words/{word}")
def remove_trigger_word(word: str) -> dict[str, Any]:
    """Remove one exact-match boost term from the dashboard manager."""
    return _domain_call(knowledge_base.remove_trigger_word, word)


@app.get("/retrieval-logs")
def retrieval_logs(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    """Return recent retrieval interactions and their optional user ratings."""
    return (
        create_supabase_client()
        .table("retrieval_logs")
        .select(RETRIEVAL_LOG_FIELDS)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
        or []
    )
