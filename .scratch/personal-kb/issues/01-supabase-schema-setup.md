# 01: Supabase schema + local dev setup

**What to build:** A running Supabase project with all tables, extensions, and indexes in place, plus a configured Python project with all dependencies installed. A developer can run a smoke-test script that inserts one entry row and queries it back — proving the full data layer works end to end before any pipeline code is written.

The schema (from the grilling session):

```sql
-- entries: the core knowledge base table
entries (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content          text NOT NULL,
  embedding        vector(1536),
  tsv              tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
  source_type      text NOT NULL,        -- 'voice_memo' | 'notion_note'
  source_file      text,
  audio_offset     float,
  word_timestamps  jsonb,
  chunk_index      int,
  chunk_strategy   text,                 -- 'pause' | 'semantic'
  tags             text[],
  mood             text,
  topic_label      text,
  moment_type      text,                 -- 'happy_moment' | 'idea' | 'reflection'
  visual_context   text,
  created_at       timestamptz DEFAULT now(),
  recorded_at      timestamptz
)

-- trigger_words: user-defined words for exact-match boost
trigger_words (
  id       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  word     text UNIQUE NOT NULL,
  added_at timestamptz DEFAULT now()
)

-- retrieval_logs: auto-logged every search call for eval set
retrieval_logs (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  query      text NOT NULL,
  results    jsonb,
  rating     int,       -- 1-5, null until rated
  comment    text,
  created_at timestamptz DEFAULT now()
)
```

**Blocked by:** None (can start immediately)

**Status:** completed

- [x] Supabase project created with pgvector extension enabled
- [x] All three tables defined with correct column types and indexes (ivfflat index on `embedding`, GIN index on `tsv` and `tags`)
- [x] `.env` file documented with required keys (`SUPABASE_URL`, `SUPABASE_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`)
- [x] `pyproject.toml` created with all dependencies (`supabase`, `openai`, `anthropic`, `fastapi`, `uvicorn`, `mcp`, `pytest`)
- [x] Smoke-test script inserts one dummy entry row and retrieves it back successfully

## Comments

- 2026-09-21: Added the Supabase migration, cloud configuration, environment template, Python project, and smoke-test script. Dependencies are installed in `.venv`. The cloud smoke test reached the configured project but received `PGRST205` because `public.entries` has not yet been created. Apply the migration with `supabase link --project-ref <project-ref>` and `supabase db push`, then rerun `python scripts/smoke_test.py`.
- 2026-09-21: The first cloud migration attempt found pgvector installed outside the `extensions` schema. The migration now searches both `public` and `extensions`, so it can use the existing extension without relocating it.
- 2026-09-22: Confirmed the linked cloud database is up to date with `supabase db push`. Ran `scripts/smoke_test.py` against the cloud project: it inserted an `entries` row and retrieved the identical row by ID.
