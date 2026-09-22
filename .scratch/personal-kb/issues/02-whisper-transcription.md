# 02: ElevenLabs transcription pipeline step

**What to build:** A CLI step that takes a single audio file (or a folder of audio files), calls the ElevenLabs Scribe v2 Speech-to-Text API, and writes a JSON transcript file alongside the audio. Running this on one real voice memo produces a complete transcript with timestamps that the chunking step can consume.

**Blocked by:** 01 — Supabase schema + local dev setup

**Status:** complete

- [x] Accepts a single audio file path or a `raw/audio/` folder as input
- [x] Calls ElevenLabs Scribe v2 and derives word- and segment-level timestamps from its response
- [x] Writes `<name>.json` transcript file containing: full text, segments array (start, end, text), words array (word, start, end)
- [x] Skips files that already have a transcript JSON (idempotent reruns)
- [x] Handles API errors gracefully with a clear error message (wrong file format, API key issue)
- [x] Tested end-to-end on real voice-memo videos from `datasets/voice_journals/`

## Comments

- 2026-09-22: Implemented `scripts/transcribe.py` with ElevenLabs Scribe v2 instead of Whisper, as requested. The command accepts one audio file or a folder, writes idempotent timestamp JSON transcripts, and has unit coverage for successful output, skipped output, API failure, and unsupported formats. Live verification remains pending an `HCAPTCHA_TOKEN` and a real audio file under `raw/audio/`.
- 2026-09-22: Completed live verification with `datasets/voice_journals/`. `After watching Harris vs AR Rahman video.mp4` produced a transcript with 50,593 text characters, 220 segments, and 4,388 words; `Life Journey.mp4` produced 55,528 text characters, 178 segments, and 4,921 words. A second run skipped both existing transcript files.
