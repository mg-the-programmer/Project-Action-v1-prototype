# 10: Trigger words MCP tools

**What to build:** Two MCP tools for managing your personal trigger word list — the words and phrases that should always surface exact-match results regardless of semantic distance. The boost is verified end-to-end: add a word, submit a journal entry containing it, confirm the exact-match entry ranks above pure-semantic alternatives.

**Blocked by:** 08 — MCP server core tools

**Status:** ready-for-agent

**New MCP tools:**

- `add_trigger_word(word)` — inserts a word or phrase into the `trigger_words` table; returns confirmation and current list size
- `list_trigger_words()` — returns the full current trigger word list with `added_at` timestamps

- [ ] `add_trigger_word` inserts into `trigger_words` table; handles duplicates gracefully (no error, just confirms already exists)
- [ ] `list_trigger_words` returns all rows ordered by `added_at` descending
- [ ] Trigger word boost in the shared retrieval layer (ticket 07) is confirmed working: add "reverse honeypot" as a trigger word, run `search_entries("teaching security")`, verify an entry containing "reverse honeypot" ranks higher than it would without the boost
- [ ] Initial seed trigger words added: words/phrases from the grilling session that Manigandan uses uniquely (e.g. "reverse honeypot", "mass-time", "3-question filter") — documented so he can verify and extend
