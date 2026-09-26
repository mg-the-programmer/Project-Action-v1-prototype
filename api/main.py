"""FastAPI endpoints for the local dashboard and phone integrations."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from mcp_server import server as knowledge_base
from scripts.transcribe import load_environment_file
from shared.clients import create_supabase_client

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


@app.post("/ingest")
def ingest(request: IngestRequest) -> dict[str, Any]:
    """Embed, tag, and store one direct journal or note entry."""
    recorded_at = request.recorded_at.isoformat() if request.recorded_at else None
    return _domain_call(knowledge_base.ingest_entry, request.text, request.source_type, recorded_at)


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
