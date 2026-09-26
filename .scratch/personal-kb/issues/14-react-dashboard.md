# 14: React + Tailwind local dashboard

**What to build:** A local React application running on `localhost:3000` that gives a full analytical view of the knowledge base — mood trends, topic distribution, happy moments gallery, live retrieval search, and eval metrics. This is the "full brain view" for deep work sessions on your laptop.

**Blocked by:** 11 — FastAPI REST layer

**Status:** in-progress

**Panels to build:**

- **Search panel**: type a query, see ranked results with source, date, mood, tags, content preview, and audio offset (displayed as a timestamp link)
- **Mood trend chart**: line chart of mood distribution over time (last 30/90/all days toggle)
- **Topic distribution**: bar or donut chart of `topic_label` counts across all entries
- **Happy moments gallery**: card grid of entries where `moment_type = 'happy_moment'`, showing `visual_context`, date, mood — foundation for the future AI image generation feature
- **Eval metrics panel**: precision/recall stats from `retrieval_logs` — rating distribution, average score, recent low-rated queries to investigate
- **Trigger word manager**: list of current trigger words with add/remove controls

- [x] React app scaffolded with Vite + Tailwind CSS
- [x] All panels consume FastAPI endpoints (no direct Supabase calls from frontend)
- [x] Search panel returns results and displays audio offset as a human-readable timestamp (e.g. "0:25 into honeypot-teaching.m4a")
- [ ] Mood trend chart renders correctly with real data
- [ ] Happy moments gallery displays entries with `moment_type = 'happy_moment'`
- [ ] App runs stably at `localhost:3000` with FastAPI running at `localhost:8000`

## Comments

2026-09-26 — Implemented the isolated `dashboard/` Vite + React + Tailwind
application. It reads entries, retrieval logs, and trigger words only through
the FastAPI REST API; it has no Supabase dependency or browser-side credential.
The dashboard includes ranked live search (including a source-offset anchor
rendered as `m:ss into source-file`), a 30/90/all mood view, topic bars, happy
moment cards, retrieval-rating metrics, and a trigger-word add/remove manager.
The removal control required a small REST addition: `DELETE /trigger-words/{word}`
delegates to the shared server boundary and is covered by API and boundary tests.

Focused build and complete Python verification:

```text
cd dashboard; npm run build
vite v5.4.21 building for production
✓ 32 modules transformed.
✓ built in 2.02s

.\.venv\Scripts\python.exe -m pytest -q
64 passed, 3 skipped, 18 warnings in 21.62s

.\.venv\Scripts\python.exe -m compileall -q api mcp_server
completed successfully (no output)

git diff --check
clean
```

Live local API data was exercised with this project on a free API port, because
the existing listener at `127.0.0.1:8000` returned `404` for both `/openapi.json`
and `/entries` and was therefore not this FastAPI app. With FastAPI at `8014`
and the dashboard built/run at `127.0.0.1:3000` using
`VITE_API_URL=http://127.0.0.1:8014`, the exact results were:

```text
dashboard_status=200
dashboard_has_root=True
entries_count=1000
retrieval_logs_count=1
trigger_words_count=3
delete_trigger_word_documented=True
search_log_id_present=True
search_results_count=3
first_result_has_audio_offset=True
first_result_source=datasets\voice_journals\ticket-05-validation\Workshop ideas.m4a.json
```

No browser-control surface was available to visually inspect React's rendered
charts/cards, and the required port 8000 was occupied by an unrelated service.
Accordingly, the three visual/port-specific acceptance items remain unchecked
and the ticket remains in progress despite the compiled UI and live API data
checks above.
