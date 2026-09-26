# 05: Store pipeline step + end-to-end ingestion

**What to build:** A CLI step that upserts enriched chunks into the `entries` table, plus a top-level ingestion script that chains the full pipeline (transcribe → chunk → embed → tag → store) for a folder of source files. Running `python ingest.py raw/audio/` on 3–5 real voice memos fully populates the Supabase `entries` table and is queryable via the Supabase dashboard.

**Blocked by:** 04 — Embed + tag pipeline step

**Status:** completed

- [x] Store step upserts enriched chunks into `entries` table; uses `source_file + chunk_index + chunk_strategy` as the upsert key to avoid duplicates on reruns
- [x] Top-level `ingest.py` CLI accepts a folder path and file type flag (`--type audio` or `--type notes`), chains all four steps in sequence
- [x] Progress is logged to console: files processed, chunks created, entries upserted
- [x] Running `ingest.py` on 3–5 real audio files produces populated `entries` rows visible in Supabase dashboard
- [x] Running `ingest.py` on exported Notion markdown files also works end-to-end
- [x] Reruns are safe — no duplicate entries created

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

2026-09-26 — Resumed after Ticket 04 switched tagging to the configured
OpenAI-compatible provider and five audio plus 137 exported Markdown samples
became available. A representative real exported Notion file completed through
all stages and stored remotely:

```text
python ingest.py 'datasets\\yt ideas notion backup' --type notes
Files processed: 1; chunks created: 1; entries upserted: 1
exit=0
```

The corresponding live Supabase identity count was `1` before rerun and `1`
after rerun (`note_unique_identities=1`), proving the upsert did not create a
duplicate. Full suite after the provider update: `python -m pytest -q` →
`21 passed in 0.78s`.

For audio, a temporary ignored validation folder contained three hard-linked
real memos (Ideation, Mg life intro, Workshop ideas). Transcription and
chunking completed for all three; the first memo fully tagged and stored two
remote rows, confirmed as:

```text
audio_rows_for_completed_first_memo= 2
audio_unique_identities= 2
audio_chunk_indices= [0, 1]
```

The provider then stopped the remaining audio tagging stage:

```text
python ingest.py 'datasets\\voice_journals\\ticket-05-validation' --type audio
Error: Error code: 429 - ... budget_exceeded ... Current cost: 985.548823, Max budget: 985.0
exit=1
```

Therefore the 3–5 real-audio full-ingestion/dashboard criterion is still not
proven. Ticket remains open until the configured OpenAI-compatible key has
budget and the three-file run plus a rerun can complete. The other checked
criteria have live Supabase evidence above.

2026-09-26 — The configured key was replaced and `OPENAI_BASE_URL` removed;
configuration verification confirmed `OPENAI_API_KEY`, `OPENAI_CHAT_MODEL`, and
`OPENAI_EMBEDDING_MODEL` are present and the base URL is absent, so standard
OpenAI is used. The three-real-memo validation folder completed end to end.
Remote Supabase verification before rerun found 14 voice-memo rows across three
sources (2, 5, and 7 chunks). After rerun it remained:

```text
audio_rows_after_rerun= 14
audio_unique_identities_after_rerun= 14
audio_sources_after_rerun= 3
audio_chunks_per_source= [2, 5, 7]
```

This proves populated remote `entries` rows for three real audio memos and no
duplicate identities on rerun. The representative exported Markdown run and
its one-row rerun evidence remain recorded above. The complete local suite also
passed: `python -m pytest -q` → `21 passed in 0.78s`.

No Ticket 05 implementation code changed during this credential-validation
resume; the prior ticket-scoped code review remains applicable. The current
follow-up changes only record verified acceptance evidence. All acceptance
criteria are now proven; ticket completed.
