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

Compare the boundaries from three to five existing voice-memo transcripts before choosing a default:

```powershell
python scripts/compare_chunking.py datasets/voice_journals --limit 3 --dry-run
python scripts/compare_chunking.py raw/audio --limit 3 --transcribe
```

The report aligns each chunk start as `chunk number: first 100 characters` and labels starts belonging to only one strategy as split/merge disagreements. Omit `--dry-run` to embed, tag, and upsert both strategies; each stays independently queryable by `chunk_strategy`. Use `--store-only` to verify strategy storage without remote enrichment.

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

## Claude Desktop MCP server

The stdio server exposes `search_entries`, `get_entry_context`, `list_by_tag`,
`list_by_date_range`, `ingest_entry`, `log_feedback`, `rate_retrieval`,
`get_persona_prompt`, and `export_memory_snapshot` to Claude Desktop.
`get_persona_prompt` returns pasteable `system_prompt` and `user_context`
formats regenerated from the latest 100 entries; `export_memory_snapshot`
returns a focused (`query`, `topic`, and optional two-item `date_range`) or
full-KB Markdown briefing. `search_entries` returns both the results and a
`log_id` that can be passed to `rate_retrieval`. It loads the project `.env`
itself, then runs as:

```powershell
.\.venv\Scripts\python.exe mcp_server\server.py
```

The Claude Desktop configuration entry uses that same interpreter and script
path. Restart Claude Desktop after changing its MCP configuration, then confirm
the `personal-kb` server has a green connected status before using its tools.

## Notion curated ideas

`push_to_notion` publishes one entry by `entry_id`, all unsynced entries with a
given `tag`, or the last seven days of unsynced `youtube-idea` and
`instagram-idea` entries. It publishes through a Notion MCP Streamable HTTP
server, not the Notion REST API. Set `NOTION_MCP_URL` to that server and
`NOTION_DATA_SOURCE_ID` to the curated database's data-source ID. The database
must provide `Title`, `Topic`, `Mood`, `Tags`, `Date`, and `Source` properties.
After Notion returns a page ID, it is stored in `entries.notion_page_id`, so a
subsequent sequential push skips the entry.

## Retrieval evaluation export

Export all rated retrieval logs with `python -m eval.export_pairs`. This writes
`eval/pairs.json` using `{query, expected_entry_ids, actual_results, rating,
comment}` objects. Ratings do not identify a single expected entry, so the
export deliberately leaves `expected_entry_ids` empty rather than inventing
ground truth. After configuring `LANGSMITH_API_KEY` and `LANGSMITH_PROJECT`,
use `python -m eval.export_pairs --push` to upload those pairs to the configured
project-named dataset (or pass `--dataset` to override that dataset name).

## Local dashboard

Start the FastAPI server on port 8000, then run the Vite dashboard in a second
terminal:

```powershell
uvicorn api.main:app --host 127.0.0.1 --port 8000
cd dashboard
npm install
npm run dev
```

The dashboard is served at `http://localhost:3000` and only calls the FastAPI
surface. To point it at a different local API port while developing, set
`VITE_API_URL`, for example `$env:VITE_API_URL='http://127.0.0.1:8014'`.

### Journal inventory and action review

The dashboard's **Voice journal inventory** groups ingested `voice_memo`
chunks by source file and exposes the canonical pause-chunk context. The
**Action suggestions for review** queue is local to Supabase: approval or
dismissal only changes that queue and never creates a Notion or other external
task.

Extraction is intentionally explicit. After applying migrations, run this
command (or use the dashboard's **Extract suggestions** button):

```powershell
python scripts/extract_actions.py
```

It uses the configured OpenAI-compatible chat provider. Each action must retain
verbatim evidence from a cited source chunk; unchanged journals are skipped on
later runs. `--dry-run` calls the extractor without writing suggestions or
extraction markers.
