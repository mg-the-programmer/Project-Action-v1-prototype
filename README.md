# Personal KB

## Local setup

1. Create and activate a Python 3.11+ virtual environment, then install the project:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -e .
   ```

2. Copy `.env.example` to `.env`. Set `SUPABASE_URL` and `SUPABASE_KEY` to the cloud project URL and anon key. `OPENAI_CHAT_MODEL`, `OPENAI_EMBEDDING_MODEL`, and `OPENAI_BASE_URL` configure the OpenAI client used by the later pipeline steps; `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, and `HCAPTCHA_TOKEN` provide their credentials.
3. Install the [Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started) as a project dependency, then authenticate, link the cloud project, and push the migration:

   ```powershell
   npm install supabase --save-dev
   npx supabase login
   npx supabase link --project-ref your-project-ref
   npx supabase db push
   ```

4. Prove the cloud data layer:

   ```powershell
   python scripts/smoke_test.py
   ```

The smoke test reads `.env` automatically and inserts then retrieves a temporary entry through the cloud Supabase API.

## Audio transcription

Transcribe one supported audio file or all supported files in a folder with ElevenLabs Scribe v2:

```powershell
python scripts/transcribe.py raw/audio
```

The command writes a `<name>.json` transcript beside each audio file, with text, timestamped segments, and timestamped words. Existing JSON transcripts are skipped.

## Schema

The `entries` table stores one knowledge-base chunk, its optional 1536-dimensional embedding, generated full-text search vector, source metadata, and labels. The vector index uses cosine distance; full-text search and tags use GIN indexes. `trigger_words` stores exact-match boost terms, while `retrieval_logs` records search results and optional 1–5 ratings.
