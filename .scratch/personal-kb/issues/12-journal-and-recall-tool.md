# 12: `journal_and_recall` MCP tool

**What to build:** A single MCP tool that is the primary daily journaling workflow: submit today's journal entry, it gets ingested into the KB, then immediately retrieves related past entries and surfaces them. One call, two actions in sequence — write then recall. This replaces manually calling `ingest_entry` followed by `search_entries`.

**Blocked by:** 08 — MCP server core tools

**Status:** ready-for-agent

**Tool:**

- `journal_and_recall(text, recorded_at?)`:
  1. Ingests the journal text via the same embed → tag → store pipeline as `ingest_entry`
  2. Immediately runs `search_entries` against the ingested text
  3. Returns: confirmation of ingestion (new entry id, tags assigned, mood detected) + related past entries ranked by blended score
  4. Past entries are clearly separated from the new entry in the response — you see what you wrote, then what it surfaced

- [ ] Tool ingests today's entry and returns its assigned tags, mood, topic_label, moment_type so you can confirm the tagging was correct
- [ ] Retrieval excludes the just-ingested entry from results (you don't want today's entry surfaced as a "past" result)
- [ ] Response format is readable in Claude Desktop: ingestion summary first, then numbered list of related past entries with source, date, mood, and content preview
- [ ] Tested with a real journal entry — past entries surface correctly
- [ ] The retrieval call is auto-logged to `retrieval_logs` (same as `search_entries`) so it feeds the eval set
