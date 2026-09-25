# 03: Chunking pipeline step (both strategies)

**What to build:** A CLI step that takes a transcript JSON (from step 02) or a Notion markdown export file and produces a JSON array of chunks ready for embedding. For audio, supports two strategies selectable via a `--strategy` flag so they can be compared. For notes, uses heading-based splitting with paragraph overflow for long sections.

**Blocked by:** 02 — Whisper transcription pipeline step

**Status:** complete

- [x] Audio chunking — `--strategy pause`: groups Whisper segments separated by >2s gap into one chunk; each chunk carries `audio_offset` (start time of first segment) and `chunk_index`
- [x] Audio chunking — `--strategy semantic`: splits on cosine similarity drop between consecutive sentence embeddings; each chunk carries `audio_offset` and `chunk_index`
- [x] Note chunking: splits on markdown heading boundaries (`##`, `###`); sections longer than ~400 words are further split at double-newline paragraph boundaries
- [x] Output is a JSON array where each item has: `content`, `source_type`, `source_file`, `audio_offset` (null for notes), `word_timestamps` (null for notes), `chunk_index`, `chunk_strategy`
- [x] Runnable on a folder of transcript JSONs and a folder of Notion markdown exports
- [x] Both audio strategies produce valid output on the same input file (needed for ticket 06 comparison)

## Comments

- 2026-09-26: Implemented and validated both chunking strategies against `datasets/voice_journals/Life Journey.json`. Pause output produced 41 contract-valid chunks; semantic output was also generated for comparison.
