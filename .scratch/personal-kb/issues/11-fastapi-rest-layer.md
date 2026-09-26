# 11: FastAPI REST layer

**What to build:** A FastAPI application exposing REST endpoints that mirror the MCP tools. This is the backend for both the React dashboard (ticket 14) and the future iPhone Shortcuts integration. It runs locally on `localhost:8000` and is verified working via curl — no public hosting yet.

**Blocked by:** 07 — Shared retrieval layer

**Status:** completed

**Endpoints to expose:**

- `POST /search` — body: `{query, top_k?, weight?}` → blended retrieval results
- `GET /entries` — query params: `tag?`, `start?`, `end?`, `source_type?` → filtered entry list
- `GET /entries/{id}/context` — surrounding chunks for a given entry
- `POST /ingest` — body: `{text, source_type, recorded_at?}` → ingests a single entry
- `GET /trigger-words` — list all trigger words
- `POST /trigger-words` — body: `{word}` → add a trigger word
- `GET /retrieval-logs` — list recent retrieval logs with ratings

- [x] All endpoints wired to the shared retrieval layer (no logic duplication with MCP server)
- [x] Server starts with `uvicorn api.main:app --reload`
- [x] `POST /search` verified via curl returning real DB results
- [x] `POST /ingest` verified: new row appears in Supabase after call
- [x] OpenAPI docs auto-generated at `localhost:8000/docs` and correct
- [x] CORS configured for `localhost:3000` (React dashboard origin)

## Comments

2026-09-26 — Implemented the local FastAPI application in `api/main.py` and
added HTTP smoke coverage in `tests/test_api.py`. Search, context, direct
ingestion, and trigger-word mutations delegate to the existing shared MCP
application boundary, so retrieval, logging, embedding, tagging, and storage
behaviour are not reimplemented by the REST surface. Entries and retrieval-log
listing use narrow, endpoint-specific Supabase reads. The API exposes the
requested OpenAPI schema automatically and permits the dashboard origin only:
`http://localhost:3000`.

Focused and full local verification:

```text
.\\.venv\\Scripts\\python.exe -m pytest tests\\test_api.py tests\\test_mcp_server.py tests\\test_feedback_eval.py -q
22 passed, 1 warning in 1.38s

.\\.venv\\Scripts\\python.exe -m pytest -q
54 passed, 3 skipped, 1 warning in 2.15s

.\\.venv\\Scripts\\python.exe -m compileall -q api
completed successfully (no output)

git diff --check
clean
```

Live HTTP verification ran `uvicorn api.main:app` on `127.0.0.1:8011` because
port 8000 was already occupied by an unrelated local listener. It used the
configured OpenAI-compatible provider and real Supabase data; the temporary
`/ingest` fixture was visible through `/entries` and then deleted.

```text
search_log_id=True
search_results=1
ingested_source_file=True
entry_visible=1
fixture_rows_deleted=1
docs_status=200
cors_origin=http://localhost:3000
```

The application remains configured to run at the specified port with
`uvicorn api.main:app --reload`; port 8000 itself could not be claimed in this
environment due to that pre-existing listener. The `/search` check necessarily
created its normal retrieval log, as required by the shared retrieval contract.

Post-review completion — Centralized the combined entry-listing operation and
its date validation in `mcp_server.server.list_entries`; the REST endpoint now
delegates to it, as do the older tag/date MCP helpers. Replaced the initial
in-process wrapper with shared `httpx` ASGI request support, and added a live
Supabase/API smoke test. It exercises every REST endpoint, verifies the
ingested fixture appears in `/entries` and its stored id appears in `/context`,
then removes its created entry, trigger word, and retrieval log.

```text
.\\.venv\\Scripts\\python.exe -m pytest tests\\test_api.py tests\\test_api_live.py tests\\test_mcp_server.py -q
18 passed, 18 provider-SDK deprecation warnings in 21.50s

.\\.venv\\Scripts\\python.exe -m pytest -q
55 passed, 3 skipped, 18 provider-SDK deprecation warnings in 21.77s

.\\.venv\\Scripts\\python.exe -m compileall -q api mcp_server tests
completed successfully (no output)

git diff --check
clean

uvicorn api.main:app --reload --host 127.0.0.1 --port 8013
started successfully; curl checks returned reload_docs=200 and reload_entries=200
```

The final Matt Pocock two-axis review against `df754a9...HEAD` had no remaining
findings. Standards: no documented-standard violations, Fowler smells, or ADR
conflicts. Spec: the shared-boundary and real-service smoke-test concerns were
resolved; all Ticket 11 requirements are met. Port 8000 remains unavailable in
this environment because of the pre-existing unrelated listener, so the same
local-only server was proved on free ports 8011–8013 instead.
