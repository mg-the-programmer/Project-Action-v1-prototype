from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

from scripts import embed, tag
from shared import clients


def test_embed_is_batched_and_idempotent() -> None:
    chunks = [{"content": "one"}, {"content": "already", "embedding": [1.0] * 1536}]
    assert embed.enrich_chunks(chunks, lambda texts: [[0.0] * 1536 for _ in texts]) == 1
    assert len(chunks[0]["embedding"]) == 1536


def test_embed_uses_batches_of_100() -> None:
    batches: list[int] = []
    chunks = [{"content": str(index)} for index in range(201)]

    def fake_embed(texts: list[str]) -> list[list[float]]:
        batches.append(len(texts))
        return [[0.0] * 1536 for _ in texts]

    assert embed.enrich_chunks(chunks, fake_embed) == 201
    assert batches == [100, 100, 1]
    assert embed.enrich_chunks(chunks, fake_embed) == 0


def test_embed_replaces_an_invalid_existing_vector() -> None:
    chunks = [{"content": "repair me", "embedding": [0.1]}]
    assert embed.enrich_chunks(chunks, lambda _: [[0.0] * 1536]) == 1
    assert chunks[0]["embedding"] == [0.0] * 1536


def test_openai_tagger_uses_the_configured_compatible_client(monkeypatch) -> None:
    client_arguments: dict[str, object] = {}
    request_arguments: dict[str, object] = {}

    class Completions:
        async def create(self, **kwargs):
            request_arguments.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"tags":["personal"],"suggested_tags":[],"mood":"curious",'
                            '"topic_label":"personal-growth","moment_type":"idea","visual_context":null}'
                        )
                    )
                ]
            )

    class AsyncOpenAI:
        def __init__(self, **kwargs):
            client_arguments.update(kwargs)
            self.chat = SimpleNamespace(completions=Completions())

    module = ModuleType("openai")
    module.AsyncOpenAI = AsyncOpenAI
    monkeypatch.setitem(sys.modules, "openai", module)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://compatible.example/v1")
    monkeypatch.setenv("OPENAI_CHAT_MODEL", "configured-chat-model")

    metadata = asyncio.run(tag.openai_tag("A personal idea."))

    assert client_arguments == {"api_key": "test-key", "base_url": "https://compatible.example/v1"}
    assert request_arguments["model"] == "configured-chat-model"
    assert request_arguments["messages"] == [{"role": "user", "content": tag.prompt("A personal idea.")}]
    assert metadata["topic_label"] == "personal-growth"


def test_embedder_uses_the_configured_compatible_client(monkeypatch) -> None:
    client_arguments: dict[str, object] = {}
    request_arguments: dict[str, object] = {}

    class Embeddings:
        def create(self, **kwargs):
            request_arguments.update(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.0] * 1536)])

    class OpenAI:
        def __init__(self, **kwargs):
            client_arguments.update(kwargs)
            self.embeddings = Embeddings()

    module = ModuleType("openai")
    module.OpenAI = OpenAI
    monkeypatch.setitem(sys.modules, "openai", module)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://compatible.example/v1")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "configured-embedding-model")

    assert clients.embed_texts(["embed me"]) == [[0.0] * 1536]
    assert client_arguments == {"api_key": "test-key", "base_url": "https://compatible.example/v1"}
    assert request_arguments == {
        "model": "configured-embedding-model",
        "input": ["embed me"],
        "dimensions": 1536,
    }


def test_tag_normalizes_unknown_values_and_preserves_suggestion() -> None:
    async def fake(_: str) -> dict[str, object]:
        return {
            "tags": ["personal", "new-term"],
            "mood": "bad",
            "topic_label": "bad",
            "moment_type": "happy_moment",
            "visual_context": "beach",
            "suggested_tags": ["new-term"],
        }

    chunks = [{"content": "a"}]
    assert asyncio.run(tag.enrich_chunks(chunks, fake)) == 1
    assert chunks[0] == {
        "content": "a",
        "tags": ["personal"],
        "mood": "neutral",
        "topic_label": "random",
        "moment_type": "happy_moment",
        "visual_context": "beach",
        "suggested_tags": ["new-term"],
    }


def test_tag_limits_concurrent_provider_calls() -> None:
    active = 0
    maximum_active = 0

    async def fake(_: str) -> dict[str, object]:
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        await asyncio.sleep(0)
        active -= 1
        return {"tags": [], "mood": "neutral", "topic_label": "random", "moment_type": None, "visual_context": None}

    chunks = [{"content": str(index)} for index in range(tag.CONCURRENCY + 3)]
    assert asyncio.run(tag.enrich_chunks(chunks, fake)) == len(chunks)
    assert maximum_active == tag.CONCURRENCY


def test_pipeline_enriches_actual_chunk_dataset_and_writes_new_tag_log(tmp_path: Path) -> None:
    source = Path("datasets/voice_journals/Life Journey.pause.chunks.json")
    chunks = json.loads(source.read_text(encoding="utf-8"))[:3]
    output = tmp_path / "life.chunks.json"
    output.write_text(json.dumps(chunks), encoding="utf-8")

    def fake_embed(texts: list[str]) -> list[list[float]]:
        assert texts == [chunk["content"] for chunk in chunks]
        return [[float(index)] * 1536 for index in range(len(texts))]

    async def fake_tag(_: str) -> dict[str, object]:
        return {
            "tags": ["personal", "life-lessons"],
            "suggested_tags": ["life-lessons"],
            "mood": "reflective",
            "topic_label": "personal-growth",
            "moment_type": "reflection",
            "visual_context": "must be discarded",
        }

    assert embed.embed_file(output, fake_embed)[1] == 3
    assert asyncio.run(tag.tag_file(output, fake_tag))[1] == 3
    enriched = json.loads(output.read_text(encoding="utf-8"))
    assert all(len(chunk["embedding"]) == 1536 for chunk in enriched)
    assert all(set(tag.TAGGING_FIELDS).issubset(chunk) for chunk in enriched)
    assert all(chunk["tags"] == ["personal"] for chunk in enriched)
    assert all(chunk["visual_context"] is None for chunk in enriched)
    assert (tmp_path / "new_tags.log").read_text(encoding="utf-8") == "life-lessons\n"

    assert embed.embed_file(output, fake_embed)[1] == 0
    assert asyncio.run(tag.tag_file(output, fake_tag))[1] == 0
    assert (tmp_path / "new_tags.log").read_text(encoding="utf-8") == "life-lessons\n"
