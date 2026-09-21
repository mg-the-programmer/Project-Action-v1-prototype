# 05: Store pipeline step + end-to-end ingestion

**What to build:** A CLI step that upserts enriched chunks into the `entries` table, plus a top-level ingestion script that chains the full pipeline (transcribe → chunk → embed → tag → store) for a folder of source files. Running `python ingest.py raw/audio/` on 3–5 real voice memos fully populates the Supabase `entries` table and is queryable via the Supabase dashboard.

**Blocked by:** 04 — Embed + tag pipeline step

**Status:** ready-for-agent

- [ ] Store step upserts enriched chunks into `entries` table; uses `source_file + chunk_index + chunk_strategy` as the upsert key to avoid duplicates on reruns
- [ ] Top-level `ingest.py` CLI accepts a folder path and file type flag (`--type audio` or `--type notes`), chains all four steps in sequence
- [ ] Progress is logged to console: files processed, chunks created, entries upserted
- [ ] Running `ingest.py` on 3–5 real audio files produces populated `entries` rows visible in Supabase dashboard
- [ ] Running `ingest.py` on exported Notion markdown files also works end-to-end
- [ ] Reruns are safe — no duplicate entries created
