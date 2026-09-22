"""Transcribe audio files with ElevenLabs Speech-to-Text.

Usage:
    python scripts/transcribe.py raw/audio
    python scripts/transcribe.py raw/audio/voice-memo.m4a
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ELEVENLABS_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
AUDIO_EXTENSIONS = {".mp3", ".mp4", ".m4a", ".wav", ".webm", ".flac", ".ogg"}


class TranscriptionApiError(RuntimeError):
    """An unsuccessful response from the transcription provider."""

    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"API error {status}: {detail}")


def load_environment_file(path: Path) -> None:
    """Load unset variables from the project's simple ``.env`` file."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def input_files(input_path: Path) -> list[Path]:
    """Return supported audio files from one file or the top level of a folder."""
    if not input_path.exists():
        raise ValueError(f"Input path does not exist: {input_path}")
    if input_path.is_file():
        if input_path.suffix.lower() not in AUDIO_EXTENSIONS:
            raise ValueError(f"Unsupported audio format: {input_path.suffix or '(no extension)'}")
        return [input_path]
    return sorted(
        (path for path in input_path.iterdir() if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS),
        key=lambda path: path.name.lower(),
    )


def normalize_transcript(data: dict[str, Any]) -> dict[str, Any]:
    """Convert the ElevenLabs word payload into the chunking pipeline contract."""
    timed_words = [
        word
        for word in data.get("words", [])
        if word.get("text", "").strip() and "start" in word and "end" in word
    ]
    words = [
        {"word": word["text"].strip(), "start": word["start"], "end": word["end"]}
        for word in timed_words
    ]
    segments: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    previous_speaker: Any = None
    for raw_word, word in zip(timed_words, words):
        speaker = raw_word.get("speaker_id")
        if current and (word["start"] - current[-1]["end"] > 1.0 or speaker != previous_speaker):
            _append_segment(segments, current)
            current = []
        current.append(word)
        previous_speaker = speaker
    if current:
        _append_segment(segments, current)
    return {"text": data.get("text", ""), "segments": segments, "words": words}


def _append_segment(segments: list[dict[str, Any]], words: list[dict[str, Any]]) -> None:
    """Append one chunking-compatible segment from consecutive timestamped words."""
    segments.append(
        {"start": words[0]["start"], "end": words[-1]["end"], "text": " ".join(word["word"] for word in words)}
    )


def post_to_elevenlabs(
    audio: Path, hcaptcha_token: str, opener: Callable[..., Any] = urlopen
) -> dict[str, Any]:
    """Send one audio file to ElevenLabs' Scribe v2 API."""
    boundary = "----personal-kb-transcription-boundary"
    content_type = mimetypes.guess_type(audio.name)[0] or "application/octet-stream"
    body = _multipart_body(audio, content_type, boundary)
    api_url = f"{ELEVENLABS_STT_URL}?{urlencode({'allow_unauthenticated': '1', 'hcaptcha_token': hcaptcha_token})}"
    request = Request(
        api_url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with opener(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise TranscriptionApiError(error.code, error.read().decode("utf-8", errors="replace")) from error
    except URLError as error:
        raise RuntimeError(f"Could not reach ElevenLabs: {error.reason}") from error


def _multipart_body(audio: Path, content_type: str, boundary: str) -> bytes:
    """Encode the minimal multipart form accepted by the Speech-to-Text API."""
    def field(name: str, value: str) -> bytes:
        return f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()

    file_header = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{audio.name}\"\r\n"
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode()
    return b"".join(
        [field("model_id", "scribe_v2"), field("diarize", "true"), file_header, audio.read_bytes(), b"\r\n", f"--{boundary}--\r\n".encode()]
    )


def transcribe_file(
    audio: Path, hcaptcha_token: str, opener: Callable[..., Any] | None = None
) -> Path | None:
    """Transcribe one file and return its JSON path, or ``None`` if it exists."""
    transcript = audio.with_suffix(".json")
    if transcript.exists():
        return None
    try:
        data = post_to_elevenlabs(audio, hcaptcha_token, opener=opener or urlopen)
    except TranscriptionApiError as error:
        raise RuntimeError(
            f"ElevenLabs transcription failed for {audio.name} (HTTP {error.status}): {error.detail}"
        ) from error
    except (URLError, OSError) as error:
        raise RuntimeError(f"ElevenLabs transcription failed for {audio.name}: {error}") from error
    transcript.write_text(json.dumps(normalize_transcript(data), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return transcript


def main() -> int:
    parser = argparse.ArgumentParser(description="Transcribe audio using ElevenLabs Scribe v2.")
    parser.add_argument("input", type=Path, help="An audio file or a folder of audio files")
    arguments = parser.parse_args()
    load_environment_file(REPOSITORY_ROOT / ".env")
    hcaptcha_token = os.environ.get("HCAPTCHA_TOKEN")
    if not hcaptcha_token:
        print("HCAPTCHA_TOKEN is required. Add it to .env or your environment.", file=sys.stderr)
        return 2
    try:
        files = input_files(arguments.input)
    except ValueError as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 2
    if not files:
        print(f"No supported audio files found in {arguments.input}")
        return 0
    failed = 0
    for audio in files:
        try:
            output = transcribe_file(audio, hcaptcha_token)
            print(f"Skipped {audio.name}" if output is None else f"Wrote {output}")
        except RuntimeError as error:
            failed += 1
            print(f"Error: {error}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
