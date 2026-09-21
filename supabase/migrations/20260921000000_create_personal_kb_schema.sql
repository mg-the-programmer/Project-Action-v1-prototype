create extension if not exists vector with schema extensions;

-- Existing Supabase projects may have pgvector installed in public instead of
-- extensions. Make either location available to this migration.
set search_path = public, extensions;

create table public.entries (
  id uuid primary key default gen_random_uuid(),
  content text not null,
  embedding vector(1536),
  tsv tsvector generated always as (to_tsvector('english', content)) stored,
  source_type text not null check (source_type in ('voice_memo', 'notion_note')),
  source_file text,
  audio_offset double precision,
  word_timestamps jsonb,
  chunk_index integer,
  chunk_strategy text check (chunk_strategy in ('pause', 'semantic')),
  tags text[],
  mood text,
  topic_label text,
  moment_type text check (moment_type in ('happy_moment', 'idea', 'reflection')),
  visual_context text,
  created_at timestamptz default now(),
  recorded_at timestamptz
);

create index entries_embedding_ivfflat_idx
  on public.entries using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create index entries_tsv_gin_idx on public.entries using gin (tsv);
create index entries_tags_gin_idx on public.entries using gin (tags);

create table public.trigger_words (
  id uuid primary key default gen_random_uuid(),
  word text unique not null,
  added_at timestamptz default now()
);

create table public.retrieval_logs (
  id uuid primary key default gen_random_uuid(),
  query text not null,
  results jsonb,
  rating integer check (rating between 1 and 5),
  comment text,
  created_at timestamptz default now()
);
