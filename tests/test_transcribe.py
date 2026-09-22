from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from scripts import transcribe


def test_transcribe_file_writes_chunking_compatible_json(tmp_path: Path) -> None:
    audio = tmp_path / "memo.mp3"
    audio.write_bytes(b"audio")
    response = Mock()
    response.read.return_value = json.dumps(
        {"text": "Hello world", "words": [{"text": "Hello", "start": 0.0, "end": 0.4}, {"text": "world", "start": 0.5, "end": 0.9}]}
    ).encode()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    opener = Mock(return_value=response)

    result = transcribe.transcribe_file(audio, "test-hcaptcha-token", opener=opener)

    assert result == audio.with_suffix(".json")
    assert json.loads(result.read_text(encoding="utf-8")) == {
        "text": "Hello world",
        "segments": [{"start": 0.0, "end": 0.9, "text": "Hello world"}],
        "words": [
            {"word": "Hello", "start": 0.0, "end": 0.4},
            {"word": "world", "start": 0.5, "end": 0.9},
        ],
    }
    request = opener.call_args.args[0]
    assert request.get_header("Xi-api-key") is None
    assert request.full_url.endswith("allow_unauthenticated=1&hcaptcha_token=test-hcaptcha-token")
    assert b'name="model_id"' in request.data and b"scribe_v2" in request.data


def test_transcribe_file_skips_existing_transcript(tmp_path: Path) -> None:
    audio = tmp_path / "memo.wav"
    audio.write_bytes(b"audio")
    transcript = audio.with_suffix(".json")
    transcript.write_text("{}", encoding="utf-8")
    opener = Mock()

    assert transcribe.transcribe_file(audio, "test-hcaptcha-token", opener=opener) is None
    opener.assert_not_called()


def test_transcribe_file_explains_api_failure(tmp_path: Path) -> None:
    audio = tmp_path / "memo.m4a"
    audio.write_bytes(b"audio")
    from urllib.error import HTTPError
    from io import BytesIO

    opener = Mock(side_effect=HTTPError("https://example.test", 401, "Unauthorized", {}, BytesIO(b"Invalid hCaptcha token")))

    with pytest.raises(RuntimeError, match="ElevenLabs transcription failed for memo.m4a.*401"):
        transcribe.transcribe_file(audio, "test-hcaptcha-token", opener=opener)


def test_input_files_rejects_unsupported_file(tmp_path: Path) -> None:
    unsupported = tmp_path / "memo.txt"
    unsupported.write_text("not audio", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported audio format"):
        transcribe.input_files(unsupported)
