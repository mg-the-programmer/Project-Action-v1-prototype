# 02: Whisper transcription pipeline step

**What to build:** A CLI step that takes a single audio file (or a folder of audio files), calls the OpenAI Whisper API with both word-level and segment-level timestamp granularities, and writes a JSON transcript file alongside the audio. Running this on one real voice memo produces a complete transcript with timestamps that the chunking step can consume.

**Blocked by:** 01 — Supabase schema + local dev setup

**Status:** ready-for-agent

- [ ] Accepts a single audio file path or a `raw/audio/` folder as input
- [ ] Calls Whisper API with `timestamp_granularities: ["word", "segment"]`
- [ ] Writes `<name>.json` transcript file containing: full text, segments array (start, end, text), words array (word, start, end)
- [ ] Skips files that already have a transcript JSON (idempotent reruns)
- [ ] Handles API errors gracefully with a clear error message (wrong file format, API key issue)
- [ ] Tested end-to-end on at least one real voice memo from `raw/audio/`
