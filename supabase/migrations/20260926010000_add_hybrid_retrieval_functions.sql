-- Keep vector and full-text ranking in Postgres so every application surface
-- calls the same retrieval implementation through shared/retrieval.py.
set search_path = public, extensions;

create or replace function public.match_entries_by_embedding(
  query_embedding vector(1536),
  match_count integer default 45
)
returns table (
  id uuid,
  content text,
  source_type text,
  source_file text,
  audio_offset double precision,
  tags text[],
  mood text,
  topic_label text,
  moment_type text,
  visual_context text,
  recorded_at timestamptz,
  semantic_score double precision
)
language sql
stable
set search_path = public, extensions
as $$
  select
    e.id, e.content, e.source_type, e.source_file, e.audio_offset, e.tags,
    e.mood, e.topic_label, e.moment_type, e.visual_context, e.recorded_at,
    (1 - (e.embedding <=> query_embedding))::double precision as semantic_score
  from public.entries as e
  where e.embedding is not null
  order by e.embedding <=> query_embedding
  limit greatest(match_count, 1);
$$;

create or replace function public.match_entries_by_text(
  search_query text,
  match_count integer default 45
)
returns table (
  id uuid,
  content text,
  source_type text,
  source_file text,
  audio_offset double precision,
  tags text[],
  mood text,
  topic_label text,
  moment_type text,
  visual_context text,
  recorded_at timestamptz,
  exact_score double precision
)
language sql
stable
set search_path = public, extensions
as $$
  with searched as (
    select websearch_to_tsquery('english', search_query) as terms
  )
  select
    e.id, e.content, e.source_type, e.source_file, e.audio_offset, e.tags,
    e.mood, e.topic_label, e.moment_type, e.visual_context, e.recorded_at,
    ts_rank_cd(e.tsv, searched.terms)::double precision as exact_score
  from public.entries as e
  cross join searched
  where e.tsv @@ searched.terms
  order by ts_rank_cd(e.tsv, searched.terms) desc, e.id
  limit greatest(match_count, 1);
$$;
