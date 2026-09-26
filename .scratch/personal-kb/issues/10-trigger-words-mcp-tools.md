# 10: Trigger words MCP tools

**What to build:** Two MCP tools for managing your personal trigger word list — the words and phrases that should always surface exact-match results regardless of semantic distance. The boost is verified end-to-end: add a word, submit a journal entry containing it, confirm the exact-match entry ranks above pure-semantic alternatives.

**Blocked by:** 08 — MCP server core tools

**Status:** completed

**New MCP tools:**

- `add_trigger_word(word)` — inserts a word or phrase into the `trigger_words` table; returns confirmation and current list size
- `list_trigger_words()` — returns the full current trigger word list with `added_at` timestamps

- [x] `add_trigger_word` inserts into `trigger_words` table; handles duplicates gracefully (no error, just confirms already exists)
- [x] `list_trigger_words` returns all rows ordered by `added_at` descending
- [x] Trigger word boost in the shared retrieval layer (ticket 07) is confirmed working: add "reverse honeypot" as a trigger word, run `search_entries("teaching security")`, verify an entry containing "reverse honeypot" ranks higher than it would without the boost
- [x] Initial seed trigger words added: words/phrases from the grilling session that Manigandan uses uniquely (e.g. "reverse honeypot", "mass-time", "3-question filter") — documented so he can verify and extend

## Comments

2026-09-26 — Implemented Ticket 10 only. Added `add_trigger_word` and
`list_trigger_words` to the stdio MCP server. Adds trim surrounding whitespace,
are unique by the database's `word` constraint, and return a duplicate
confirmation without an error. The insert uses conflict-ignore semantics after
the lookup, which also handles a concurrent add safely. List results contain
`word` and `added_at`, newest first.

Focused local verification:

```text
.\\.venv\\Scripts\\python.exe -m pytest tests\\test_mcp_server.py tests\\test_retrieval.py -q
17 passed, 3 skipped in 0.98s

.\\.venv\\Scripts\\python.exe -m compileall -q mcp_server shared
completed successfully (no output)

git diff --check
clean
```

Live Supabase and MCP stdio verification used the configured project. No
Anthropic client or credential was used. The initial persisted seed list is
`reverse honeypot`, `mass-time`, and `3-question filter`.

```text
seed_confirmations=[{'word': 'reverse honeypot', 'already_exists': False, 'count': 1}, {'word': 'mass-time', 'already_exists': False, 'count': 2}, {'word': '3-question filter', 'already_exists': False, 'count': 3}]
seed_terms_present=True
ordered_desc=True
trigger_word_count=3

live_trigger_bonus_applied=True
live_trigger_entry_ranked_above_alternative=True
temporary_entries_deleted=True

mcp_trigger_tools_registered=True
mcp_duplicate_call_error=False
mcp_list_call_error=False
```

The live ranking check inserted two isolated exact-search entries for
`teaching security`, asserted that the `reverse honeypot` entry received the
configured trigger bonus and ranked over its non-trigger alternative, then
deleted both temporary entries. The seed terms remain intentionally persisted.

The post-implementation spec review identified that this first ranking fixture
bypassed journal ingestion. A subsequent real MCP stdio check closed that gap:
it called `ingest_entry` twice through the configured OpenAI-compatible
embedding and chat provider, then called `search_entries` with the blended
weight. The trigger entry ranked above the semantic teaching-security
alternative. Both generated entries and that retrieval log were deleted:

```text
mcp_ingest_then_search_trigger_ranked_above_semantic_alternative=True
mcp_journal_fixture_entries_deleted=True
mcp_journal_fixture_log_deleted=True
```

Post-implementation two-axis review against `6eda730...bb973a6` found no
standards violations or actionable Fowler smells. Its initial spec finding
about the missing MCP ingestion path is resolved by the live check above; no
code change was needed.
