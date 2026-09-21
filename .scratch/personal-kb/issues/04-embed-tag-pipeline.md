# 04: Embed + tag pipeline step

**What to build:** Two CLI steps — one that generates embeddings for each chunk, one that calls Claude Haiku 4.5 to assign metadata — that together take raw chunks and produce fully enriched entries ready for storage. Running both on a batch of chunks produces a JSON file with embeddings and metadata filled in for every chunk.

**Blocked by:** 03 — Chunking pipeline step

**Status:** ready-for-agent

- [ ] Embed step calls `text-embedding-3-large` at 1536 dimensions for each chunk's `content`; adds `embedding` array to each chunk JSON
- [ ] Tag step sends each chunk to Claude Haiku 4.5 with a structured prompt that extracts: `tags` (from seed list: `youtube-idea`, `instagram-idea`, `business`, `cybersecurity`, `genai`, `personal`, `shower-thought`, `daily-journal`, `content-script`, `example`, `personal-scenario`), `mood` (from: `excited`, `happy`, `reflective`, `frustrated`, `curious`, `neutral`), `topic_label` (from: `content-creation`, `cybersecurity`, `ai-ml`, `personal-growth`, `business-ideas`, `random`), `moment_type` (`happy_moment` | `idea` | `reflection` | null), `visual_context` (short scene description for happy_moment entries, null otherwise)
- [ ] Haiku prompt instructs the model it may suggest a new tag not in the seed list — new suggestions are logged to a `new_tags.log` file for periodic review
- [ ] Both steps are idempotent — skip chunks that already have embeddings / tags
- [ ] Batch processes efficiently (embeddings in batches of 100, tagging with concurrency limit to avoid rate limits)
- [ ] Output is enriched chunk JSON with all fields populated
