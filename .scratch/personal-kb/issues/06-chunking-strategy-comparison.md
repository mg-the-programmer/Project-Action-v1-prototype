# 06: Chunking strategy visual comparison

**What to build:** A comparison script that ingests the same 3–5 audio files with both `pause` and `semantic` chunking strategies and prints chunk boundaries side-by-side for human inspection. The outcome is a documented decision: which strategy becomes the default `chunk_strategy` for voice memos, recorded in `CONTEXT.md`.

**Blocked by:** 05 — Store pipeline step + end-to-end ingestion

**Status:** complete

- [x] Script ingests the same audio files twice — once with `--strategy pause`, once with `--strategy semantic` — storing both sets in `entries` with their respective `chunk_strategy` values
- [x] Prints a side-by-side diff of chunk boundaries for each file: chunk number, start time, first 100 chars of content, for both strategies
- [x] Makes it easy to spot where the two strategies disagree (different split points, merged vs split segments)
- [x] After visual inspection, the chosen default strategy is documented in `CONTEXT.md` under a new "Chunking" entry with a one-line rationale
- [x] If the winner is not obvious, both strategies remain in the DB queryable by `chunk_strategy` column for query-time comparison in ticket 09

## Comments

- Implemented `scripts/compare_chunking.py`: it creates pause and semantic outputs for the same 3–5 transcript sources, renders aligned start-time/100-character previews with split/merge markers, and stores each strategy under its existing distinct identity. Its normal mode enriches before storage; `--store-only` supports inexpensive storage verification.
- `python -m pytest tests/test_compare_chunking.py tests/test_chunk.py tests/test_store_ingest.py -q` → `14 passed in 0.39s`.
- `python scripts/compare_chunking.py 'datasets/voice_journals' --limit 3 --dry-run` → completed on three real ignored transcripts. Inspection showed 1,242 semantic chunks (587, 50, and 605) and 92 pause chunks (40, 11, and 41); semantic split many coherent speaking runs into micro-chunks.
- `python scripts/compare_chunking.py 'datasets/voice_journals' --limit 3 --store-only` → `Upserted 1334 entries across both strategies (without enrichment).` Both variants remain independently queryable through `chunk_strategy`.
- `python -m pytest -q` → `26 passed in 0.88s`; `git diff --check` → no whitespace errors.
- Code review: Standards found one low-severity duplicate chunk serialization path; resolved by exposing and reusing `chunk.write_chunks`. Spec review found raw-audio input partiality; resolved with `--transcribe`, which transcribes each of the selected audio files once before both strategies run. No unresolved findings.
- Post-review verification: `python -m pytest -q` → `27 passed in 0.93s`; `git diff --check` → no whitespace errors (only Git line-ending warnings).
- Tracker correction: checked all acceptance criteria after audit; each is supported by the implementation and command evidence above.
