"""Create the external clients used by ingestion without leaking credentials."""
from __future__ import annotations

import os
from typing import Any

from supabase import create_client


def create_supabase_client() -> Any:
    """Return the configured Supabase client."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required for storage")
    return create_client(url, key)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts with the project-selected 1536-dimensional OpenAI model."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for embedding")
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=os.environ.get("OPENAI_BASE_URL") or None)
    response = client.embeddings.create(
        model=os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large"),
        input=texts,
        dimensions=1536,
    )
    return [item.embedding for item in response.data]
