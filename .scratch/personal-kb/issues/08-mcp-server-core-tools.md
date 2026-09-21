# 08: MCP server — core retrieval tools

**What to build:** A stdio MCP server exposing the five core tools that make the knowledge base queryable from Claude Desktop. After this ticket, Claude Desktop has both the Notion MCP and this KB MCP connected simultaneously, and a live query returns real past entries from the Supabase DB.

**Blocked by:** 07 — Shared retrieval layer

**Status:** ready-for-agent

**Tools to expose:**

- `search_entries(query, top_k?, weight?)` — blended hybrid retrieval via the shared retrieval layer; returns ranked results with source, timestamp, mood, tags, audio_offset
- `get_entry_context(id)` — fetches the surrounding chunks from the same source file (same `source_file`, adjacent `chunk_index` values) so the full original thought can be read, not just the matching fragment
- `list_by_tag(tag)` — returns all entries carrying a specific tag, ordered by `recorded_at` descending
- `list_by_date_range(start, end)` — returns all entries within a date range, ordered by `recorded_at` descending
- `ingest_entry(text, source_type, recorded_at?)` — adds a new text entry directly from Claude chat (embed → tag → store pipeline for a single entry); useful for live journaling without touching the CLI

**Blocked by:** 07 — Shared retrieval layer

- [ ] MCP server starts via stdio transport and registers all five tools
- [ ] Each tool is wired to the shared retrieval layer or direct Supabase queries
- [ ] Server is added to Claude Desktop's MCP config and verified connected (green status)
- [ ] A live query in Claude Desktop (`search_entries("cybersecurity teaching"`) returns real entries from the DB
- [ ] `ingest_entry` round-trips: text typed in Claude Desktop appears as a new `entries` row in Supabase
