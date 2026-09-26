-- Suggestions are internal review records. They deliberately do not reference
-- Notion (or any other task provider), so a human approval remains local.
create table public.journal_action_items (
  id uuid primary key default gen_random_uuid(),
  source_file text not null,
  source_entry_id uuid not null references public.entries(id) on delete cascade,
  action_key text not null,
  wording text not null check (length(trim(wording)) > 0),
  evidence text not null check (length(trim(evidence)) > 0),
  status text not null default 'suggested'
    check (status in ('suggested', 'approved', 'dismissed')),
  extracted_at timestamptz not null default now(),
  reviewed_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (source_file, action_key)
);

create index journal_action_items_source_file_idx
  on public.journal_action_items (source_file);
create index journal_action_items_status_idx
  on public.journal_action_items (status, created_at desc);

-- A source fingerprint is stored only after extraction succeeds. Re-running the
-- explicit backfill therefore makes no model call or duplicate suggestions for
-- unchanged ingested journals.
create table public.journal_action_extractions (
  source_file text primary key,
  source_fingerprint text not null,
  extracted_at timestamptz not null default now()
);
