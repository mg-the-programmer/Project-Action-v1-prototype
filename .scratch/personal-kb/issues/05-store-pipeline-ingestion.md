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

## Comments

2026-09-26 — Implemented `scripts/store.py` (Supabase upsert on
`source_file,chunk_index,chunk_strategy`) and `ingest.py` for audio and Notion
Markdown folders. Added the unique-index/`heading`-strategy migration
`20260926000000_support_note_upserts.sql`; applied it to the linked remote
project successfully:

```text
npx supabase db push
Applying migration 20260926000000_support_note_upserts.sql...
Finished supabase db push.
```

Focused and full local validation:

```text
python -m pytest tests/test_store_ingest.py tests/test_embed_tag.py tests/test_chunk.py tests/test_transcribe.py -q
19 passed in 0.82s

python -m pytest -q
19 passed in 0.69s
```

The store test uses the real local `datasets/voice_journals/Life Journey.pause.chunks.json`
sample and verifies its stable identities are sent through the upsert boundary.
The notes orchestration test verifies heading chunks run through embed, tag, and
store using deterministic provider/client seams.

Live validation was attempted twice with the available real audio folder:

```text
python ingest.py datasets\\voice_journals --type audio
Error: Error code: 401 - ... authentication_error ... invalid x-api-key
```

The folder has two audio files, not the requested 3–5. The invalid configured
`ANTHROPIC_API_KEY` stops the tag stage, so no entries were upserted and neither
the live-audio/dashboard criterion nor the real exported-Notion end-to-end
criterion is proven. Rerun safety against a live table is also unproven, though
the unique index and upsert test cover the intended mechanism. Ticket remains
open until valid tagging credentials plus 3–5 audio files and an exported Notion
Markdown sample are available.

2026-09-26 — Code review against `f7ffcbf...HEAD`: standards review found no
hard violation and one duplicate embedding-adapter judgement call; fixed by
making `scripts.chunk.openai_embedder` use `shared.clients.embed_texts`. Spec
review found only the unproven live end-to-end acceptance criterion documented
above. Post-fix full test command: `python -m pytest -q` → `19 passed in 0.69s`.
