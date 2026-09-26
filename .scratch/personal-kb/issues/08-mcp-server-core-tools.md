# 08: MCP server — core retrieval tools

**What to build:** A stdio MCP server exposing the five core tools that make the knowledge base queryable from Claude Desktop. After this ticket, Claude Desktop has both the Notion MCP and this KB MCP connected simultaneously, and a live query returns real past entries from the Supabase DB.

**Blocked by:** 07 — Shared retrieval layer

**Status:** in-progress

**Tools to expose:**

- `search_entries(query, top_k?, weight?)` — blended hybrid retrieval via the shared retrieval layer; returns ranked results with source, timestamp, mood, tags, audio_offset
- `get_entry_context(id)` — fetches the surrounding chunks from the same source file (same `source_file`, adjacent `chunk_index` values) so the full original thought can be read, not just the matching fragment
- `list_by_tag(tag)` — returns all entries carrying a specific tag, ordered by `recorded_at` descending
- `list_by_date_range(start, end)` — returns all entries within a date range, ordered by `recorded_at` descending
- `ingest_entry(text, source_type, recorded_at?)` — adds a new text entry directly from Claude chat (embed → tag → store pipeline for a single entry); useful for live journaling without touching the CLI

**Blocked by:** 07 — Shared retrieval layer

- [x] MCP server starts via stdio transport and registers all five tools
- [x] Each tool is wired to the shared retrieval layer or direct Supabase queries
- [ ] Server is added to Claude Desktop's MCP config and verified connected (green status)
- [x] A live MCP query (`search_entries("cybersecurity teaching")`) returns real entries from the DB
- [x] `ingest_entry` round-trips through MCP: a submitted text entry appears as a new `entries` row in Supabase

## Comments

2026-09-26 — Added `mcp_server/server.py`, a stdio FastMCP server with the five
ticket tools. `search_entries` delegates to `shared.retrieval`; context and
list tools use narrowly scoped Supabase queries; `ingest_entry` runs the
configured OpenAI-compatible embedding/tagging pipeline then stores one
`notion_note` or `voice_memo` chunk. `recorded_at` is now preserved by the
existing store boundary. The server loads the local `.env` itself so the Claude
Desktop configuration contains no credentials.

Focused and full local verification:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_mcp_server.py tests\test_store_ingest.py -q
9 passed in 1.29s

.\.venv\Scripts\python.exe -m pytest -q
37 passed, 3 skipped in 1.97s

.\.venv\Scripts\python.exe -m compileall -q mcp_server scripts\store.py
completed successfully (no output)

git diff --check
clean
```

The existing Claude Desktop configuration was updated with the `personal-kb`
server command and JSON-validated. A direct MCP stdio client verified protocol
startup and exact registration:

```text
stdio_registered_tools=get_entry_context,ingest_entry,list_by_date_range,list_by_tag,search_entries
```

Live end-to-end checks used the configured OpenAI-compatible provider and real
Supabase. The search was sent over MCP stdio and returned 15 content blocks;
the temporary ingestion row was verified then deleted:

```text
mcp_live_search_error=False
mcp_live_structured_type=dict
mcp_live_structured_keys=result
mcp_live_content_blocks=15

mcp_live_ingest_error=False
mcp_live_ingest_rows=1
mcp_live_ingest_round_trip=True
mcp_live_ingest_fixture_deleted=True
```

The only remaining acceptance item is the Claude Desktop UI's green connected
status. The configuration is installed and the identical stdio command has
been protocol-verified, but this environment cannot inspect Claude Desktop's
UI; restart Claude Desktop and confirm that visual status before marking the
ticket completed.

Post-review fixes and final verification:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_mcp_server.py -q
7 passed in 1.15s

.\.venv\Scripts\python.exe -m pytest -q
39 passed, 3 skipped in 2.01s

.\.venv\Scripts\python.exe -m compileall -q mcp_server scripts\store.py
completed successfully (no output)

git diff --check
clean
```

The required two-axis review compared `eadaabd...a96aa91`. Standards found one
`CONTEXT.md` conflict: `voice_memo` ingestion incorrectly labelled the entry
with the `heading` strategy. The server now selects `pause` for voice memos and
has a regression test. Spec review found that context was overly narrowed to a
strategy and omitted `recorded_at` made direct journal entries unbrowseable by
date; context now follows exactly the specified same-source adjacent-index
rule, and absent `recorded_at` is set to current UTC. Post-fix standards and
spec re-reviews found no remaining code-level findings. The green UI status is
still the only outstanding acceptance item.
