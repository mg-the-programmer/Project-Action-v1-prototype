# 09: Feedback capture + eval logging

**What to build:** Every retrieval call is automatically logged to `retrieval_logs`. Two new MCP tools let you rate and comment on results from inside Claude Desktop. After 10–15 rated retrievals, `eval/pairs.json` is populated and a LangSmith project is connected for precision/recall tracking.

**Blocked by:** 08 — MCP server core tools

**Status:** in-progress

**New MCP tools:**

- `log_feedback(query, results, rating, comment)` — manually logs a retrieval interaction with a 1–5 rating and free-text comment; used when you want to annotate outside the normal search flow
- `rate_retrieval(log_id, rating, comment)` — annotates an existing `retrieval_logs` row; `search_entries` auto-logs every call and returns a `log_id` so you can immediately rate: "that top result was wrong, `rate_retrieval(log_id=X, rating=2, comment='missed the honeypot entry')`"

- [x] `search_entries` auto-inserts a row into `retrieval_logs` (query, results as JSONB, timestamp) on every call and returns `log_id` in its response
- [x] `rate_retrieval(log_id, rating, comment)` updates the matching `retrieval_logs` row
- [x] `log_feedback` MCP tool works as a standalone annotation
- [x] A script reads rated rows from `retrieval_logs` and writes `eval/pairs.json` in LangSmith dataset format: `[{query, expected_entry_ids, actual_results, rating, comment}]`
- [ ] LangSmith project created, API key in `.env`, script confirmed to push eval pairs to the project
- [ ] After 10–15 live retrievals rated in Claude Desktop, `eval/pairs.json` has at least 10 entries

## Comments

2026-09-26 — Implemented Ticket 09 only. `search_entries` now logs each
successful retrieval and returns `{log_id, results}`. Added standalone
`log_feedback` and `rate_retrieval` MCP tools, with validation for JSON result
objects, 1–5 ratings, nonblank comments, and unknown log ids. The new
`eval.export_pairs` module reads rated rows and writes the required pair shape.
It deliberately emits an empty `expected_entry_ids` list: the current schema
contains a whole-retrieval rating but no per-entry relevance label, so deriving
ground truth from retrieved results would be fabricated. The optional
`--push` path uses the declared LangSmith client only after `LANGSMITH_API_KEY`
and `LANGSMITH_PROJECT` are configured.

Focused and full local verification:

```text
.\.venv\Scripts\python.exe -m pytest tests\test_mcp_server.py tests\test_feedback_eval.py -q
13 passed in 1.53s

.\.venv\Scripts\python.exe -m pytest -q
45 passed, 3 skipped in 1.73s

.\.venv\Scripts\python.exe -m compileall -q mcp_server shared eval
completed successfully (no output)

git diff --check
clean
```

Live checks used the configured OpenAI-compatible embedding provider and the
real Supabase database. Each temporary row was deleted after assertion:

```text
live_search_auto_logged=True
live_search_result_count=1
live_search_log_deleted=True
live_feedback_log_created=True
live_feedback_rating_updated=True
live_eval_pair_serialized=True
live_feedback_fixture_deleted=True
```

The actual exporter also completed against the configured database:

```text
python -m eval.export_pairs --output <temporary file>
Wrote 0 rated retrieval pairs to <temporary file>
live_rated_log_export_count=0
```

`LANGSMITH_API_KEY` and `LANGSMITH_PROJECT` were not present in `.env` when
checked by name only, so no LangSmith project was created and no credentialed
push was attempted. There are also no live Claude Desktop ratings yet; both
remaining acceptance items stay unchecked. The LangSmith client import boundary
was verified after installing the declared local dependency, but that is not a
substitute for a configured-project push.

Post-implementation two-axis review against `d0e4ede...9b1025e` found no
standards violations or actionable Fowler smells. Spec review confirmed that
the two unchecked external/live criteria remain partial; it also found the
upload path had only checked `LANGSMITH_PROJECT` while using a separate default
dataset name. The path now defaults its dataset name to the configured project
name (with an explicit `--dataset` override). The review also identified that
the existing whole-retrieval rating cannot provide per-entry ground truth for
precision/recall; that limitation is recorded above rather than fabricated.

The post-fix standards and spec re-reviews against `d0e4ede...c45ab8b` found
no remaining actionable code-level findings. Final local verification after the
review fix was `46 passed, 3 skipped` and `git diff --check` was clean.
