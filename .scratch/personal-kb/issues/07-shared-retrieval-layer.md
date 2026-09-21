# 07: Shared retrieval layer

**What to build:** A shared Python module that performs blended hybrid retrieval — semantic (pgvector) + exact-match (tsvector) with trigger word boosting — and returns ranked, deduplicated results. This module is the single retrieval implementation consumed by both the MCP server (ticket 08) and the FastAPI layer (ticket 11). A test against real DB data confirms results are ranked correctly and trigger words surface exact matches.

**Blocked by:** 05 — Store pipeline step + end-to-end ingestion

**Status:** ready-for-agent

- [ ] `search_entries(query, top_k=15, weight=0.7)` function: embeds the query, runs pgvector similarity search, runs tsvector full-text search, merges and deduplicates results, applies trigger word boost (entries whose content contains a trigger word rank higher), returns top_k results ordered by blended score
- [ ] Each result includes: `id`, `content`, `source_type`, `source_file`, `audio_offset`, `tags`, `mood`, `topic_label`, `moment_type`, `visual_context`, `recorded_at`, `blended_score`
- [ ] `weight` parameter controls semantic vs exact-match balance (0.0 = pure exact, 1.0 = pure semantic, 0.7 default)
- [ ] Trigger word boost: any result whose content contains a word from the `trigger_words` table gets a score bonus applied before final ranking
- [ ] Integration test queries the real DB with a known query and asserts the expected entry appears in top results
- [ ] Module has no MCP or HTTP dependencies — pure DB logic only
