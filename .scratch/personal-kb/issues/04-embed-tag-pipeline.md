# 04: Embed + tag pipeline step

**What to build:** Two CLI steps — one that generates embeddings for each chunk, one that calls the configured OpenAI-compatible chat model to assign metadata — that together take raw chunks and produce fully enriched entries ready for storage. Running both on a batch of chunks produces a JSON file with embeddings and metadata filled in for every chunk.

**Blocked by:** 03 — Chunking pipeline step

**Status:** complete

- [x] Embed step calls `text-embedding-3-large` at 1536 dimensions for each chunk's `content`; adds `embedding` array to each chunk JSON
- [x] Tag step sends each chunk to the configured OpenAI-compatible chat model with a structured prompt that extracts: `tags` (from seed list: `youtube-idea`, `instagram-idea`, `business`, `cybersecurity`, `genai`, `personal`, `shower-thought`, `daily-journal`, `content-script`, `example`, `personal-scenario`), `mood` (from: `excited`, `happy`, `reflective`, `frustrated`, `curious`, `neutral`), `topic_label` (from: `content-creation`, `cybersecurity`, `ai-ml`, `personal-growth`, `business-ideas`, `random`), `moment_type` (`happy_moment` | `idea` | `reflection` | null), `visual_context` (short scene description for happy_moment entries, null otherwise)
- [x] Tagging prompt instructs the model it may suggest a new tag not in the seed list — new suggestions are logged to a `new_tags.log` file for periodic review
- [x] Both steps are idempotent — skip chunks that already have embeddings / tags
- [x] Batch processes efficiently (embeddings in batches of 100, tagging with concurrency limit to avoid rate limits)
- [x] Output is enriched chunk JSON with all fields populated

## Comments

- 2026-09-26: Implemented `scripts/embed.py` and `scripts/tag.py`. The embedder uses `text-embedding-3-large` with `dimensions=1536`, batches pending chunks in groups of 100, and preserves valid existing embeddings. The tagger uses Claude Haiku 4.5 with a JSON-only taxonomy prompt, limits concurrent requests to 5, writes the required metadata fields, keeps proposed non-seed tags out of stored `tags`, and records them once in the output directory's `new_tags.log`.
- 2026-09-26: `python -m pytest tests/test_embed_tag_store_retrieval.py -q` — 7 passed in 0.24s. This includes an end-to-end enrichment test using the first three chunks from `datasets/voice_journals/Life Journey.pause.chunks.json`, with provider seams substituted so no credentials or external writes were required; it verifies 1536-value embeddings, all metadata fields, taxonomy proposal logging, and idempotent reruns.
- 2026-09-26: `python -m pytest -q` — 17 passed in 0.74s.
- 2026-09-26: `python -m compileall -q scripts/embed.py scripts/tag.py` — completed successfully (no output).
- 2026-09-26: Two-axis review completed against the ticket-scoped working tree (the files were untracked, so `git diff HEAD...HEAD` was empty). Standards review found no documented-standard violations and one maintainability suggestion; renamed the local coroutine from `one` to `tag_chunk`. Spec review found invalid retained embeddings could bypass the 1536-dimension contract; `scripts/embed.py` now re-embeds malformed vectors, with a regression test.
- 2026-09-26: `python -m pytest tests/test_embed_tag.py -q` — 6 passed. `python -m pytest -q` — 23 passed. `python -m compileall -q scripts/embed.py scripts/tag.py` — completed successfully (no output).
- 2026-09-26: Ticket-scoped implementation and review evidence committed with `git commit -m "Implement embed and tag pipeline"`.
- 2026-09-26: User-authorized provider substitution: tagging now uses only the configured OpenAI-compatible client (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_CHAT_MODEL`); embedding continues to use `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_EMBEDDING_MODEL`. The Anthropic dependency and example secret are removed. Validation and review follow in this adaptation commit.
- 2026-09-26: Provider-adaptation two-axis review found no standards or specification findings. The review verified that tagging has no Anthropic import, key, or model setting and that the existing embedding boundary keeps `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_EMBEDDING_MODEL`, and `dimensions=1536`. Added tests capture both configured client calls.
- 2026-09-26: `python -m pytest tests/test_embed_tag.py -q` — 8 passed in 0.27s. `python -m pytest -q` — 21 passed in 0.67s. `python -m compileall -q scripts/embed.py scripts/tag.py` — completed successfully (no output). The scoped provider-reference scan returned no matches.
