# 15: Persona + memory export MCP tools

**What to build:** Two MCP tools that make the knowledge base portable — usable in any chat interface (Claude.ai, ChatGPT) without MCP connected. `get_persona_prompt` derives your writing voice and identity from your journal entries and returns a pasteable system prompt. `export_memory_snapshot` returns a condensed markdown briefing of relevant past entries. Both formats (system prompt and user context block) are returned for every call.

**Blocked by:** 07 — Shared retrieval layer, 08 — MCP server core tools

**Status:** ready-for-agent

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

- [ ] `get_persona_prompt()` with no args returns both `system_prompt` and `user_context` strings derived from real entries
- [ ] Persona output includes at least: domain expertise, communication style, 3–5 recurring phrases/analogies, active projects
- [ ] `export_memory_snapshot()` with no args returns a readable markdown summary of the full KB
- [ ] `export_memory_snapshot(query="cybersecurity teaching")` returns a focused summary of relevant entries
- [ ] Both tools verified by pasting their output into a fresh Claude.ai session and confirming the AI has accurate context about Manigandan's background and projects
