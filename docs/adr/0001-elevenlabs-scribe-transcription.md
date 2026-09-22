# Use ElevenLabs Scribe v2 for voice-memo transcription

**Status:** accepted

The voice-memo ingestion pipeline uses ElevenLabs Scribe v2 rather than the originally planned OpenAI Whisper API. Scribe provides the timestamped word response from which the pipeline derives its stable transcript contract (full text, words, and segments), and it is invoked through the unauthenticated endpoint with an hCaptcha token supplied as `HCAPTCHA_TOKEN`.

## Considered Options

- OpenAI Whisper with native word- and segment-level timestamp granularities.
- ElevenLabs Scribe v2 with timestamped words and derived segments.

## Consequences

The chunking pipeline must depend on the stored transcript JSON contract, not on a provider-specific response shape. Changing transcription providers later requires changing the adapter and re-verifying timestamps, but should not require changing downstream chunking.
