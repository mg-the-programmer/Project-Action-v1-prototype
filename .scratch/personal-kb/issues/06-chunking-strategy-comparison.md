# 06: Chunking strategy visual comparison

**What to build:** A comparison script that ingests the same 3–5 audio files with both `pause` and `semantic` chunking strategies and prints chunk boundaries side-by-side for human inspection. The outcome is a documented decision: which strategy becomes the default `chunk_strategy` for voice memos, recorded in `CONTEXT.md`.

**Blocked by:** 05 — Store pipeline step + end-to-end ingestion

**Status:** ready-for-agent

- [ ] Script ingests the same audio files twice — once with `--strategy pause`, once with `--strategy semantic` — storing both sets in `entries` with their respective `chunk_strategy` values
- [ ] Prints a side-by-side diff of chunk boundaries for each file: chunk number, start time, first 100 chars of content, for both strategies
- [ ] Makes it easy to spot where the two strategies disagree (different split points, merged vs split segments)
- [ ] After visual inspection, the chosen default strategy is documented in `CONTEXT.md` under a new "Chunking" entry with a one-line rationale
- [ ] If the winner is not obvious, both strategies remain in the DB queryable by `chunk_strategy` column for query-time comparison in ticket 09
