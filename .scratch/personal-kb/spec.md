# Spec: Personal Knowledge Base / Journal Retrieval System

**Status:** ready-for-agent

---

## Problem Statement

Manigandan (AI Engineer, PwC India, GenAI/cybersecurity intersection) records voice memos and writes notes constantly — shower thoughts, video ideas, personal frameworks, business ideas, daily journal entries. These sit as "dumb storage" and are never resurfaced when they are most needed. When preparing for a workshop, drafting a YouTube script, or evaluating a new tool, the relevant past ideas, personal analogies, and exact phrasing he coined exist somewhere in his history but are unreachable in the moment.

The existing content pipeline (Notion → voice burst → ElevenLabs transcription → Claude) is too slow, too costly (per-call transcription), and still requires manual retrieval. There is no system that closes the loop between what he has thought before and what he is thinking now.

The core need is not just search — it is **word-for-word recall with original voice preserved**. Paraphrased semantic similarity alone is not sufficient; when Manigandan coined the phrase "reverse honeypot" as a teaching analogy, he needs to retrieve that exact phrase, in his own words, when preparing a cybersecurity workshop. The same applies to personal frameworks ("3-question filter"), business scenarios, and happy memories he wants to relive.

---

## Solution

A personal knowledge base that:

1. **Ingests** voice memos (via ElevenLabs Scribe v2 transcription with word/segment timestamps) and text notes (Notion markdown exports) into a Supabase Postgres database
2. **Retrieves** entries using hybrid search — semantic (pgvector) for conceptual similarity and exact-match (tsvector) for word-for-word precision — with a user-defined trigger word list that boosts exact matches for personally significant terms
3. **Surfaces** related past entries automatically after each journal submission via a `journal_and_recall` tool in Claude Desktop
4. **Exposes** the knowledge base through three surfaces: an MCP server for Claude Desktop, a FastAPI REST layer for the local dashboard and future phone integration, and a Notion push for mobile-accessible curated content
5. **Enables portability** — a persona prompt and memory snapshot tool lets the full context travel into any chat interface (Claude.ai, ChatGPT) without MCP
6. **Measures retrieval quality** through auto-logged feedback rated in real usage, feeding a LangSmith eval set

---

## User Stories

### Ingestion

1. As Manigandan, I want to drop audio files into a folder and run one command, so that all my voice memos are transcribed and stored in the knowledge base without manual steps.
2. As Manigandan, I want transcription to capture word-level timestamps alongside segment-level timestamps, so that I can later jump to the exact moment in the original audio where an idea was spoken.
3. As Manigandan, I want to export my Notion notes as markdown and ingest them with the same pipeline, so that both voice and text sources live in one unified knowledge base.
4. As Manigandan, I want the ingestion pipeline to be idempotent, so that rerunning it on the same files does not create duplicate entries.
5. As Manigandan, I want each chunk to be automatically tagged with topic, mood, moment type, and visual context by an LLM at ingestion time, so that I do not have to manually categorise my entries.
6. As Manigandan, I want to be able to suggest new tags during tagging review that are not in the seed taxonomy, so that the vocabulary grows with my actual content rather than being locked to a predefined list.
7. As Manigandan, I want to type a journal entry directly in Claude Desktop and have it ingested immediately, so that journaling in my primary tool also populates the knowledge base.

### Retrieval

8. As Manigandan, I want to search the knowledge base with a natural language query and get the top 15 blended results, so that both conceptually related and word-for-word matching entries surface together.
9. As Manigandan, I want to control the balance between semantic and exact-match retrieval with a weight parameter, so that I can tune recall vs. precision for different query types.
10. As Manigandan, I want certain personally significant words and phrases (trigger words) to always boost exact-match results, so that my own coined terms — "reverse honeypot", "mass-time", "3-question filter" — are never missed.
11. As Manigandan, I want to add and list trigger words from inside Claude Desktop, so that I can maintain my personal vocabulary list without leaving my journaling environment.
12. As Manigandan, I want to fetch the surrounding chunks from the same source when a result surfaces, so that I can read the full original thought rather than just the matching fragment.
13. As Manigandan, I want to browse all entries by tag, so that I can explore everything I have ever thought about a specific topic.
14. As Manigandan, I want to browse entries by date range, so that I can review what I was thinking about last week or last month.

### Journal and Recall Workflow

15. As Manigandan, I want to submit today's journal entry and immediately see related past entries in one operation, so that the recall happens automatically without a separate search step.
16. As Manigandan, I want the ingestion confirmation to show me the tags, mood, and topic assigned to my entry, so that I can verify the auto-tagging was correct.
17. As Manigandan, I want the related past entries to exclude the entry I just submitted, so that today's writing does not appear in my historical recall.

### Feedback and Eval

18. As Manigandan, I want every retrieval call to be automatically logged, so that I never lose a query/result pair that could be valuable for evaluating retrieval quality.
19. As Manigandan, I want to rate a retrieval result with a score and comment from inside Claude Desktop, so that my live usage naturally builds the eval set without a separate annotation step.
20. As Manigandan, I want my rated retrieval logs exported to LangSmith as an eval dataset, so that I can measure precision/recall quantitatively before investing in phone integration.

### Trigger Words

21. As Manigandan, I want to add a trigger word and immediately have it applied to future retrievals, so that newly coined terms are protected from the moment I identify them.
22. As Manigandan, I want to see my full trigger word list with the date each was added, so that I can audit and prune it over time.

### Dashboard

23. As Manigandan, I want a local React dashboard showing mood trends over time, so that I can see how my emotional patterns correlate with topic clusters.
24. As Manigandan, I want a topic distribution chart across all entries, so that I can see what I think about most.
25. As Manigandan, I want a happy moments gallery showing entries tagged as `happy_moment` with their visual context, so that I can browse emotionally significant memories and use them as the foundation for future AI image generation.
26. As Manigandan, I want a live retrieval search interface in the dashboard, so that I can test queries and tune retrieval without opening Claude Desktop.
27. As Manigandan, I want an eval metrics panel showing rating distributions and recent low-rated queries, so that I know where retrieval is failing.
28. As Manigandan, I want a trigger word manager in the dashboard, so that I can add and remove trigger words with a UI rather than a chat command.
29. As Manigandan, I want search results in the dashboard to show audio offsets as human-readable timestamps (e.g. "0:25 into honeypot-teaching.m4a"), so that I can jump to the exact audio moment.

### Notion Integration

30. As Manigandan, I want a `push_to_notion` tool that pushes entries tagged as `youtube-idea` or `instagram-idea` to a Notion database, so that actionable content ideas are accessible on my phone in Notion.
31. As Manigandan, I want pushed entries to appear only once in Notion even if I run the push multiple times, so that my Notion database does not accumulate duplicates.
32. As Manigandan, I want the Notion database to show title, topic, mood, tags, and date for each entry, so that I can quickly scan and act on ideas from my phone.

### Persona and Memory Portability

33. As Manigandan, I want a tool that generates a system prompt derived from my journal entries, so that I can paste it into any Claude.ai or ChatGPT session and have that AI understand who I am and how I think.
34. As Manigandan, I want a user context block format alongside the system prompt, so that I have the right format for interfaces that do not have a dedicated system prompt field.
35. As Manigandan, I want a memory snapshot tool that returns a condensed markdown summary of relevant past entries for a given query or topic, so that I can carry context from the knowledge base into any chat session.
36. As Manigandan, I want the full memory snapshot (no query) to summarise my top recurring themes, active projects, and key decisions, so that any AI I hand it to gets a full briefing on my background.
37. As Manigandan, I want the persona prompt to always reflect my latest entries when regenerated, so that it stays fresh as my thinking evolves.

### REST API

38. As Manigandan, I want a local FastAPI server exposing all knowledge base operations as REST endpoints, so that the React dashboard and future iPhone Shortcuts integration have a stable API contract to consume.
39. As Manigandan, I want the API docs auto-generated and available at `/docs`, so that I can inspect and test endpoints without memorising the interface.

---

## Implementation Decisions

### Data layer

- **Database**: Supabase cloud (Postgres + pgvector extension). Single `entries` table is the source of truth for all knowledge base content. Notion is a display layer, not a source of truth.
- **Schema** (settled in grilling session):
  - `entries`: `id`, `content`, `embedding vector(1536)`, `tsv tsvector` (generated, stored), `source_type` (`voice_memo` | `notion_note`), `source_file`, `audio_offset float`, `word_timestamps jsonb`, `chunk_index int`, `chunk_strategy text` (`pause` | `semantic`), `tags text[]`, `mood text`, `topic_label text`, `moment_type text` (`happy_moment` | `idea` | `reflection`), `visual_context text`, `notion_page_id text`, `created_at timestamptz`, `recorded_at timestamptz`
  - `trigger_words`: `id`, `word text UNIQUE`, `added_at timestamptz`
  - `retrieval_logs`: `id`, `query text`, `results jsonb`, `rating int` (1–5, nullable), `comment text`, `created_at timestamptz`
- **Indexes**: ivfflat index on `embedding`; GIN index on `tsv` and `tags`

### Transcription

- **Provider**: ElevenLabs Scribe v2 (switched from Whisper during implementation — same interface contract: word/segment timestamps preserved)
- **Timestamp granularities**: both word-level and segment-level captured in a single API call. Segment timestamps stored in `audio_offset`; word-level stored in `word_timestamps` (JSONB) for future audio-emotion feature.

### Chunking

- **Voice memos**: two strategies implemented and compared side-by-side before committing to a default:
  - `pause`: groups Whisper/ElevenLabs segments separated by >2s gap into one chunk
  - `semantic`: splits on cosine similarity drop between consecutive sentence embeddings
- **Text notes**: heading-based splitting (`##`, `###` boundaries), with sections longer than ~400 words further split at paragraph boundaries
- **`chunk_strategy` column** preserves which strategy produced each chunk, enabling query-time comparison in the eval phase
- Default strategy recorded in `CONTEXT.md` after the visual comparison in ticket 06

### Embedding and tagging

- **Embedding model**: OpenAI `text-embedding-3-large` at **1536 dimensions** (Matryoshka truncation from 3072). Chosen for quality at personal scale; privacy tradeoff accepted.
- **Tagging model**: Claude Haiku 4.5 — fast, cheap, sufficient for classification
- **Taxonomy** (semi-controlled — LLM can suggest new tags, logged for review):
  - Tags (multi-valued): `youtube-idea`, `instagram-idea`, `business`, `cybersecurity`, `genai`, `personal`, `shower-thought`, `daily-journal`, `content-script`, `example`, `personal-scenario`
  - Mood (single): `excited`, `happy`, `reflective`, `frustrated`, `curious`, `neutral`
  - Topic label (dominant theme): `content-creation`, `cybersecurity`, `ai-ml`, `personal-growth`, `business-ideas`, `random`

### Retrieval

- **Hybrid blended search**: pgvector semantic (cosine similarity) + tsvector exact-match, merged and deduplicated, with a tunable `weight` parameter (default 0.7 semantic / 0.3 exact)
- **Trigger word boost**: entries whose content contains a word from `trigger_words` receive a score bonus applied before final ranking
- **Default top-k**: 15 results per query
- **No re-ranking** at this phase — added later if eval metrics show precision problems

### Architecture

- **Shared retrieval layer** (`shared/retrieval.py`): single implementation of hybrid search, trigger word boost, and result formatting. Consumed by both the MCP server and FastAPI — no logic duplication.
- **MCP server** (stdio transport): Claude Desktop integration. Tools: `search_entries`, `get_entry_context`, `list_by_tag`, `list_by_date_range`, `ingest_entry`, `log_feedback`, `rate_retrieval`, `add_trigger_word`, `list_trigger_words`, `journal_and_recall`, `push_to_notion`, `get_persona_prompt`, `export_memory_snapshot`
- **FastAPI REST layer** (`localhost:8000`): mirrors MCP tools as REST endpoints; serves React dashboard and future iPhone Shortcuts integration. CORS configured for `localhost:3000`.
- **React + Tailwind dashboard** (`localhost:3000`): local-only analytical view. Panels: search, mood trends, topic distribution, happy moments gallery, eval metrics, trigger word manager.
- **Notion push**: entries tagged `youtube-idea` / `instagram-idea` pushed to a Notion database via Notion MCP. `notion_page_id` column prevents duplicate pushes.
- **Language**: Python (pipeline, MCP server, FastAPI). React + Vite + Tailwind (dashboard).
- **Project layout**: `cli/` (pipeline steps), `mcp_server/`, `api/`, `shared/`, `raw/audio/`, `raw/notes/`, `eval/`

### Eval

- Auto-log every retrieval call to `retrieval_logs`
- `rate_retrieval` MCP tool annotates logs from inside Claude Desktop during live usage
- First 10–15 rated retrievals exported to `eval/pairs.json` in LangSmith dataset format
- LangSmith used for precision/recall measurement before phone integration investment

---

## Testing Decisions

**What makes a good test here:** tests should verify observable outputs and side effects, not implementation internals. The primary seam is the shared retrieval layer — test that given known DB content, a query returns the expected entries in the expected rank order. Pipeline steps are tested by their file outputs (transcript JSON shape, chunk JSON shape, enriched chunk JSON shape), not their internal logic.

**Modules to test:**

- **Shared retrieval layer** (`shared/retrieval.py`): integration tests against real Supabase data. Given a known set of entries, assert that: (a) a semantic query returns conceptually related entries in top results; (b) a query containing a trigger word boosts exact-match entries above pure-semantic alternatives; (c) `weight=0.0` returns only exact-match results; `weight=1.0` returns only semantic results.
- **Transcription step** (`cli/transcribe.py`): unit tests for output shape (transcript JSON has `text`, `segments`, `words` fields). Live API call tested manually with a real audio file.
- **Chunking step** (`cli/chunk.py`): unit tests with fixture transcript JSON — assert correct chunk boundaries for `pause` strategy (>2s gap splits), `semantic` strategy (similarity drop splits), and heading-based note splitting.
- **Tagging step** (`cli/tag.py`): unit tests mock the Haiku API call — assert that valid `tags`, `mood`, `topic_label`, `moment_type` values are extracted from a known response; assert that unknown tags are logged to `new_tags.log`.
- **MCP tools**: tested end-to-end by live use in Claude Desktop during Phase 2 (interactive qualitative testing). No unit tests for tool registration boilerplate.
- **FastAPI endpoints**: smoke tests using `httpx` test client — assert each endpoint returns a 200 with the expected response shape against real DB data.

---

## Out of Scope

- **iPhone Shortcuts integration**: deferred until retrieval accuracy is validated by LangSmith eval in Phase 3. The FastAPI layer is built and ready; the phone-side integration is not.
- **Persona generation feature** (writing-style fingerprint for LLM output): the `get_persona_prompt` tool generates a context snapshot from existing entries, but a full persona model (style transfer, fine-tuning) is not in scope.
- **Notion auto-categorization dashboard** (YouTube / Business / Funny topic buckets): entries are pushed to Notion with their existing tags; no automatic Notion-side categorization or bucket views.
- **AI image generation from happy moments**: the `moment_type`, `visual_context`, and happy moments gallery lay the groundwork, but image generation and iPhone widget delivery are not built in this phase.
- **Public API hosting**: all services run locally (`localhost`). No deployment to VPS, cloud functions, or public endpoints.
- **Obsidian integration**: considered and ruled out — Supabase is the source of truth; Notion handles the curated mobile surface.
- **Multi-user support**: this is a single-user personal system.
- **Re-ranking**: not implemented in this phase. Added later if LangSmith eval shows precision problems after retrieval quality is established.

---

## Further Notes

- **Retrieval priority is recall over precision**: Manigandan's stated concern is "never miss a relevant old note when it is needed most." The default top-k of 15 and the trigger word boost both serve this. Precision tuning comes after the eval set is populated.
- **ElevenLabs vs Whisper**: ticket 02 was implemented with ElevenLabs Scribe v2 instead of the originally planned local Whisper. The interface contract is identical (word + segment timestamps). The cost (~$0.006/min) was accepted as the tradeoff for simplicity. This is recorded here so future decisions about transcription cost are made with full context.
- **Chunking strategy is still open**: tickets 03–05 build both strategies; ticket 06 resolves which becomes the default through visual comparison. `CONTEXT.md` is updated with the outcome.
- **Happy moments are a distinct feature class**: entries with `moment_type = 'happy_moment'` and `visual_context` are the seed data for a future AI image generation + iPhone widget pipeline. Tagging them correctly at ingestion is important — the visual_context description should be rich enough for an image generator to work from.
- **Persona tools are regeneration-based, not incremental**: `get_persona_prompt` and `export_memory_snapshot` always read from the current DB state. There is no cached persona that needs invalidation — just regenerate when needed.
