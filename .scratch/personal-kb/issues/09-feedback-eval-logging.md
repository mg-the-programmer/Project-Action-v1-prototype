# 09: Feedback capture + eval logging

**What to build:** Every retrieval call is automatically logged to `retrieval_logs`. Two new MCP tools let you rate and comment on results from inside Claude Desktop. After 10–15 rated retrievals, `eval/pairs.json` is populated and a LangSmith project is connected for precision/recall tracking.

**Blocked by:** 08 — MCP server core tools

**Status:** ready-for-agent

**New MCP tools:**

- `log_feedback(query, results, rating, comment)` — manually logs a retrieval interaction with a 1–5 rating and free-text comment; used when you want to annotate outside the normal search flow
- `rate_retrieval(log_id, rating, comment)` — annotates an existing `retrieval_logs` row; `search_entries` auto-logs every call and returns a `log_id` so you can immediately rate: "that top result was wrong, `rate_retrieval(log_id=X, rating=2, comment='missed the honeypot entry')`"

- [ ] `search_entries` auto-inserts a row into `retrieval_logs` (query, results as JSONB, timestamp) on every call and returns `log_id` in its response
- [ ] `rate_retrieval(log_id, rating, comment)` updates the matching `retrieval_logs` row
- [ ] `log_feedback` MCP tool works as a standalone annotation
- [ ] A script reads rated rows from `retrieval_logs` and writes `eval/pairs.json` in LangSmith dataset format: `[{query, expected_entry_ids, actual_results, rating, comment}]`
- [ ] LangSmith project created, API key in `.env`, script confirmed to push eval pairs to the project
- [ ] After 10–15 live retrievals rated in Claude Desktop, `eval/pairs.json` has at least 10 entries
