# Personal KB

## Local setup

1. Create and activate a Python 3.11+ virtual environment, then install the project:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -e .
   ```

2. Copy `.env.example` to `.env`. Set `SUPABASE_URL` and `SUPABASE_KEY` to the cloud project URL and anon key. `OPENAI_CHAT_MODEL`, `OPENAI_EMBEDDING_MODEL`, and `OPENAI_BASE_URL` configure the OpenAI-compatible clients used by the later pipeline steps; `OPENAI_API_KEY` and `HCAPTCHA_TOKEN` provide their credentials.
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

## Chunking

Create embedding-ready chunks from transcript JSON files or Notion Markdown exports:

```powershell
python scripts/chunk.py raw/audio --strategy pause
python scripts/chunk.py raw/audio --strategy semantic
python scripts/chunk.py raw/notes
```

Audio outputs are written beside each transcript as `<name>.pause.chunks.json` or `<name>.semantic.chunks.json`, so both strategies can be compared on the same source. Markdown outputs use `<name>.chunks.json`. The semantic strategy requires `OPENAI_API_KEY` and uses the configured `OPENAI_EMBEDDING_MODEL` (defaulting to `text-embedding-3-large`).

## Full ingestion

Run the complete pipeline for a folder of audio files or exported Notion Markdown:

```powershell
python ingest.py raw/audio --type audio
python ingest.py raw/notes --type notes
```

Each run logs files processed, chunks created, and entries upserted. Entries are
upserted by source file, chunk index, and chunking strategy, so rerunning a
folder does not create duplicate rows.

## Schema

The `entries` table stores one knowledge-base chunk, its optional 1536-dimensional embedding, generated full-text search vector, source metadata, and labels. The vector index uses cosine distance; full-text search and tags use GIN indexes. `trigger_words` stores exact-match boost terms, while `retrieval_logs` records search results and optional 1–5 ratings.
