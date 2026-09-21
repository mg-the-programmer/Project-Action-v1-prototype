# 11: FastAPI REST layer

**What to build:** A FastAPI application exposing REST endpoints that mirror the MCP tools. This is the backend for both the React dashboard (ticket 14) and the future iPhone Shortcuts integration. It runs locally on `localhost:8000` and is verified working via curl — no public hosting yet.

**Blocked by:** 07 — Shared retrieval layer

**Status:** ready-for-agent

**Endpoints to expose:**

- `POST /search` — body: `{query, top_k?, weight?}` → blended retrieval results
- `GET /entries` — query params: `tag?`, `start?`, `end?`, `source_type?` → filtered entry list
- `GET /entries/{id}/context` — surrounding chunks for a given entry
- `POST /ingest` — body: `{text, source_type, recorded_at?}` → ingests a single entry
- `GET /trigger-words` — list all trigger words
- `POST /trigger-words` — body: `{word}` → add a trigger word
- `GET /retrieval-logs` — list recent retrieval logs with ratings

- [ ] All endpoints wired to the shared retrieval layer (no logic duplication with MCP server)
- [ ] Server starts with `uvicorn api.main:app --reload`
- [ ] `POST /search` verified via curl returning real DB results
- [ ] `POST /ingest` verified: new row appears in Supabase after call
- [ ] OpenAPI docs auto-generated at `localhost:8000/docs` and correct
- [ ] CORS configured for `localhost:3000` (React dashboard origin)
