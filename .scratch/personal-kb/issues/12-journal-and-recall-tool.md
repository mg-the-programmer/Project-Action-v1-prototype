# 12: `journal_and_recall` MCP tool

**What to build:** A single MCP tool that is the primary daily journaling workflow: submit today's journal entry, it gets ingested into the KB, then immediately retrieves related past entries and surfaces them. One call, two actions in sequence — write then recall. This replaces manually calling `ingest_entry` followed by `search_entries`.

**Blocked by:** 08 — MCP server core tools

**Status:** in-progress

**Tool:**

- `journal_and_recall(text, recorded_at?)`:
  1. Ingests the journal text via the same embed → tag → store pipeline as `ingest_entry`
  2. Immediately runs `search_entries` against the ingested text
  3. Returns: confirmation of ingestion (new entry id, tags assigned, mood detected) + related past entries ranked by blended score
  4. Past entries are clearly separated from the new entry in the response — you see what you wrote, then what it surfaced

- [x] Tool ingests today's entry and returns its assigned tags, mood, topic_label, moment_type so you can confirm the tagging was correct
- [x] Retrieval excludes the just-ingested entry from results (you don't want today's entry surfaced as a "past" result)
- [ ] Response format is readable in Claude Desktop: ingestion summary first, then numbered list of related past entries with source, date, mood, and content preview
- [x] Tested with a real journal entry — past entries surface correctly
- [x] The retrieval call is auto-logged to `retrieval_logs` (same as `search_entries`) so it feeds the eval set

## Comments

2026-09-26 — Implemented `journal_and_recall(text, recorded_at?)` in the MCP
server. It reuses the normal OpenAI-compatible embed → tag → Supabase store
path as a `notion_note`, resolves the stored entry ID, performs hybrid
retrieval, excludes that fresh ID, logs only the historical results, and returns
an ingestion section followed by numbered, compact past-entry summaries
(source, date, mood, preview, and blended score). The ingestion result includes
`id`, `tags`, `mood`, `topic_label`, and `moment_type`.

Focused and full local verification:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_mcp_server.py -q
14 passed in 0.93s

.\.venv\Scripts\python.exe -m pytest -q
57 passed, 3 skipped, 18 warnings in 21.72s

.\.venv\Scripts\python.exe -m compileall -q mcp_server
completed successfully (no output)

git diff --check
clean
```

Live verification used the configured OpenAI-compatible provider and the real
Supabase project with a unique temporary journal entry. It asserted storage,
metadata, exclusion, and retrieval-log creation, then deleted both temporary
records:

```text
& .\.venv\Scripts\python.exe -c $ticket12Code
journal_entry_id_returned=True
journal_entry_excluded=True
journal_metadata_returned=True
related_past_entry_count=14
retrieval_log_created=True
temporary_journal_entry_deleted=True
temporary_retrieval_log_deleted=True
```

The direct tool workflow and structured response are proven by the live run and
MCP registration test. The remaining unchecked item is visual confirmation of
the formatting inside the Claude Desktop UI, which is unavailable in this
environment; leave this ticket incomplete until that UI check is performed.

Post-review correction: the spec review found that fetching 15 rows and then
excluding the fresh entry could leave only 14 past entries. The tool now fetches
16 candidates, excludes the fresh ID, then returns the top 15 historical rows.
The regression test asserts that `top_k=16` is used. A second real-provider,
real-Supabase run verified the corrected count and cleanup:

```text
& .\.venv\Scripts\python.exe -c $ticket12Code
journal_entry_id_returned=True
journal_entry_excluded=True
related_past_entry_count=15
retrieval_log_created=True
temporary_journal_entry_deleted=True
temporary_retrieval_log_deleted=True
```

Required two-axis review, comparing `8f8578e...67a4fa7`:

```text
Standards: 0 findings. No documented-standard breaches or Fowler baseline smells.
Spec (initial): 1 finding — post-retrieval exclusion could reduce historical results to 14.
Spec (after correction): resolved by requesting 16 candidates and limiting after exclusion.
```

Final two-axis re-review of amended commit `9d576f5` (same fixed point
`8f8578e`):

```text
Standards: 0 findings.
Spec: the top-15 exclusion issue is resolved; the only remaining finding is the
unverified Claude Desktop visual-readability acceptance item already left unchecked.
```
