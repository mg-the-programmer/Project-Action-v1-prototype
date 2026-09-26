-- Markdown chunks use the heading strategy and every source chunk has a
-- stable identity so the ingestion pipeline can safely be rerun.
alter table public.entries drop constraint if exists entries_chunk_strategy_check;
alter table public.entries add constraint entries_chunk_strategy_check
  check (chunk_strategy in ('pause', 'semantic', 'heading'));

create unique index if not exists entries_source_chunk_strategy_unique_idx
  on public.entries (source_file, chunk_index, chunk_strategy);
