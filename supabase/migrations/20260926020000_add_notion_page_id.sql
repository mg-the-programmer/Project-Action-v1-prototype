-- A populated value is the durable idempotency marker for the Notion display
-- layer. Supabase remains the source of truth for the entry itself.
alter table public.entries
  add column if not exists notion_page_id text;

create unique index if not exists entries_notion_page_id_unique_idx
  on public.entries (notion_page_id)
  where notion_page_id is not null;
