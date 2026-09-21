# 14: React + Tailwind local dashboard

**What to build:** A local React application running on `localhost:3000` that gives a full analytical view of the knowledge base — mood trends, topic distribution, happy moments gallery, live retrieval search, and eval metrics. This is the "full brain view" for deep work sessions on your laptop.

**Blocked by:** 11 — FastAPI REST layer

**Status:** ready-for-agent

**Panels to build:**

- **Search panel**: type a query, see ranked results with source, date, mood, tags, content preview, and audio offset (displayed as a timestamp link)
- **Mood trend chart**: line chart of mood distribution over time (last 30/90/all days toggle)
- **Topic distribution**: bar or donut chart of `topic_label` counts across all entries
- **Happy moments gallery**: card grid of entries where `moment_type = 'happy_moment'`, showing `visual_context`, date, mood — foundation for the future AI image generation feature
- **Eval metrics panel**: precision/recall stats from `retrieval_logs` — rating distribution, average score, recent low-rated queries to investigate
- **Trigger word manager**: list of current trigger words with add/remove controls

- [ ] React app scaffolded with Vite + Tailwind CSS
- [ ] All panels consume FastAPI endpoints (no direct Supabase calls from frontend)
- [ ] Search panel returns results and displays audio offset as a human-readable timestamp (e.g. "0:25 into honeypot-teaching.m4a")
- [ ] Mood trend chart renders correctly with real data
- [ ] Happy moments gallery displays entries with `moment_type = 'happy_moment'`
- [ ] App runs stably at `localhost:3000` with FastAPI running at `localhost:8000`
