# 07: Shared retrieval layer

**What to build:** A shared Python module that performs blended hybrid retrieval — semantic (pgvector) + exact-match (tsvector) with trigger word boosting — and returns ranked, deduplicated results. This module is the single retrieval implementation consumed by both the MCP server (ticket 08) and the FastAPI layer (ticket 11). A test against real DB data confirms results are ranked correctly and trigger words surface exact matches.

**Blocked by:** 05 — Store pipeline step + end-to-end ingestion

**Status:** completed

- [x] `search_entries(query, top_k=15, weight=0.7)` function: embeds the query, runs pgvector similarity search, runs tsvector full-text search, merges and deduplicates results, applies trigger word boost (entries whose content contains a trigger word rank higher), returns top_k results ordered by blended score
- [x] Each result includes: `id`, `content`, `source_type`, `source_file`, `audio_offset`, `tags`, `mood`, `topic_label`, `moment_type`, `visual_context`, `recorded_at`, `blended_score`
- [x] `weight` parameter controls semantic vs exact-match balance (0.0 = pure exact, 1.0 = pure semantic, 0.7 default)
- [x] Trigger word boost: any result whose content contains a word from the `trigger_words` table gets a score bonus applied before final ranking
- [x] Integration test queries the real DB with a known query and asserts the expected entry appears in top results
- [x] Module has no MCP or HTTP dependencies — pure DB logic only

## Comments

- Applied `supabase/migrations/20260926010000_add_hybrid_retrieval_functions.sql` and `supabase/migrations/20260926011000_return_all_hybrid_candidates.sql` with `npx supabase db push`: both completed successfully.
- `RUN_LIVE_SUPABASE_TESTS=1 python -m pytest tests/test_retrieval.py -q`: 8 passed. This exercised the configured OpenAI-compatible embedding provider, the live Supabase pgvector/tsvector RPCs, an ignored voice-journal fixture already present in the database, an isolated semantic fixture, and a temporary trigger-word fixture. Both temporary fixtures were deleted in `finally`.
- `python -m pytest -q`: 32 passed, 3 skipped when the opt-in live tests were not enabled. The live run above had only SDK deprecation warnings.
- `git diff --check`: clean.
- Code review against `f6d9ab4...9b44861`: standards review found no documented-standard violations; it suggested renaming `_add_component`, which was changed to `_merge_scored_row`. Spec review found incorrect whole-word regex boundaries and incomplete live ranking/trigger evidence; the regex was corrected and the two live tests above were added. The explicit SQL return-field duplication was retained as the intentional cross-boundary database contract.
- Final review against `f6d9ab4...8569c41`: standards review found the integration-marker text incorrectly promised read-only tests; the marker now documents temporary-fixture cleanup. No baseline code smells were actionable.
- Final spec review found candidate truncation could make blended top-k approximate and requested an explicit ranking comparison. The follow-up migration now returns all candidates for exact personal-scale ranking, and live tests prove the trigger fixture outranks its unboosted twin plus a provider-embedded fixture ranks first under pure semantic search.
- Post-fix standards review found no issues. Post-fix spec review required trigger boosts to be excluded from `weight=1.0`; this was corrected so pure semantic ranking is unmodified by exact-match boosts.
