# Personal KB

## Local setup

1. Install the [Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started) and Docker Desktop.
2. Create and activate a Python 3.11+ virtual environment, then install the project:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -e .
   ```

3. Copy `.env.example` to `.env`. `SUPABASE_URL` and `SUPABASE_KEY` must point to the local stack or a Supabase project. `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` are retained for the later ingestion and retrieval steps.
4. Start the local database. Supabase applies `supabase/migrations/20260921000000_create_personal_kb_schema.sql` during startup:

   ```powershell
   supabase start
   ```

5. Set `SUPABASE_URL` and `SUPABASE_KEY` from the `supabase start` output, then prove the data layer:

   ```powershell
   python scripts/smoke_test.py
   ```

For a clean local database, run `supabase db reset`. To apply the migration to a linked development project, run `supabase db push`.

## Schema

The `entries` table stores one knowledge-base chunk, its optional 1536-dimensional embedding, generated full-text search vector, source metadata, and labels. The vector index uses cosine distance; full-text search and tags use GIN indexes. `trigger_words` stores exact-match boost terms, while `retrieval_logs` records search results and optional 1–5 ratings.
