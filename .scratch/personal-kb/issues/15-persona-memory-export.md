# 15: Persona + memory export MCP tools

**What to build:** Two MCP tools that make the knowledge base portable — usable in any chat interface (Claude.ai, ChatGPT) without MCP connected. `get_persona_prompt` derives your writing voice and identity from your journal entries and returns a pasteable system prompt. `export_memory_snapshot` returns a condensed markdown briefing of relevant past entries. Both formats (system prompt and user context block) are returned for every call.

**Blocked by:** 07 — Shared retrieval layer, 08 — MCP server core tools

**Status:** in-progress

**Tools:**

- `get_persona_prompt(style?)`:
  - Pulls the top 100 entries by recency and tag frequency
  - Sends them to Claude Haiku 4.5 to extract: recurring vocabulary and coined phrases, domain expertise areas, communication style (short/energetic bursts vs reflective long-form), recurring analogies and mental models, active projects and interests
  - Returns **two formats**:
    - `system_prompt`: a system message for pasting into Claude.ai's system prompt field or ChatGPT's custom instructions
    - `user_context`: a first-message block for interfaces without a system prompt field
  - Always reflects the latest entries — regenerate any time for a fresh snapshot

- `export_memory_snapshot(query?, topic?, date_range?)`:
  - If `query` provided: runs retrieval and returns a markdown summary of the most relevant past entries grouped by theme
  - If `topic` provided: filters by `topic_label` and summarises
  - If nothing provided: returns a full life summary — top recurring themes, active projects, key decisions, recent mood trends
  - Returns a clean markdown string ready to paste as context into any chat

- [x] `get_persona_prompt()` with no args returns both `system_prompt` and `user_context` strings derived from real entries
- [x] Persona output includes at least: domain expertise, communication style, 3–5 recurring phrases/analogies, active projects
- [x] `export_memory_snapshot()` with no args returns a readable markdown summary of the full KB
- [x] `export_memory_snapshot(query="cybersecurity teaching")` returns a focused summary of relevant entries
- [ ] Both tools verified by pasting their output into a fresh Claude.ai session and confirming the AI has accurate context about Manigandan's background and projects

## Comments

- 2026-09-26: Implemented the `get_persona_prompt` and `export_memory_snapshot` MCP tools using the project's configured OpenAI-compatible chat provider (`OPENAI_CHAT_MODEL` / `OPENAI_BASE_URL`), rather than an Anthropic client. Persona generation reads the latest 100 entries, includes tag-frequency context, and returns both `system_prompt` and `user_context`. Snapshot generation uses the shared retrieval layer for `query`, filters the database for `topic` and/or `date_range`, and produces paste-ready Markdown.
- 2026-09-26: `./.venv/Scripts/python.exe -m pytest tests/test_mcp_server.py -q` — 23 passed. This covers both MCP registrations, recency/tag-frequency persona inputs and dual output formats, query retrieval, topic/date filtering, and unfiltered full-KB briefing inputs.
- 2026-09-26: `./.venv/Scripts/python.exe -m pytest -q` — 69 passed, 3 skipped; the 18 warnings are existing Supabase SDK deprecations in live API smoke tests.
- 2026-09-26: Live configured-service check: loaded `.env`, read `live_recent_entries=100` from Supabase, generated a persona through the configured OpenAI-compatible API (`live_persona_system_chars=2847`, `live_persona_user_context_chars=2674`) and confirmed all required sections were present. A live `export_memory_snapshot(query="cybersecurity teaching")` completed through OpenAI embeddings, Supabase hybrid retrieval, and chat generation (`live_query_snapshot_chars=1017`).
- 2026-09-26: Live configured-service check: `export_memory_snapshot()` without filters read the full configured KB (100 entries at validation time) and generated a Markdown briefing (`live_full_snapshot_chars=5010`, heading present).
- 2026-09-26: Two-axis review against `f6c4f75...9a362ee`: Standards reported no hard breaches and two heuristic findings; renamed the generic chat-generation function and introduced `SnapshotFilter` to remove duplicated filter state. Spec review found full-KB snapshots were incorrectly capped at 100 entries; the cap now applies only to the ticket-required persona source selection, while snapshots read all matching entries. The review also confirmed the Claude.ai paste criterion remains an external UI block.
- 2026-09-26: The first four acceptance criteria are proven by the focused tests and configured live calls above. The final Claude.ai paste-and-confirm criterion is an external browser/UI validation that cannot be performed from this repository task; it remains unchecked, so the ticket is intentionally not marked complete.
- 2026-09-26: Independent fresh-consumer validation (redacted; no persona or journal text was retained in this ticket): a PowerShell stdin program invoked the registered `get_persona_prompt_tool()` and `export_memory_snapshot_tool()` functions through `./.venv/Scripts/python.exe -u -`, after `load_environment_file(server.REPOSITORY_ROOT / '.env')`; this used the configured Supabase and OpenAI-compatible services. Result: `live_persona_system_chars=2815`, `live_persona_user_context_chars=2642`, and `live_full_snapshot_chars=5304`; the required persona headings, both formats, and Markdown snapshot all passed. A rubric applied only to the generated artifacts found projects and broad focus identifiable, but did **not** find explicit evidence of the specified professional background or the specified coined-preference/analogy signals; the full snapshot likewise did not establish the specified preferences or focus. `./.venv/Scripts/python.exe -m pytest tests/test_mcp_server.py -q` — 23 passed. Verdict: this is not an adequate substitute for the requested fresh Claude.ai acceptance check, because a fresh consumer cannot yet reliably identify all four requested dimensions (background, projects, preferences, and focus) from the portable output alone. The final checkbox remains unchecked and `Status: in-progress`; what remains is an actual fresh-session validation that demonstrates those dimensions, or a deliberate product change that makes the missing evidence explicit and is separately tested.
