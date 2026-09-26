"""Create the external clients used by ingestion without leaking credentials."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _without_repository_supabase_package() -> None:
    """Allow importing the installed SDK despite the local ``supabase`` directory."""
    sys.path[:] = [path for path in sys.path if Path(path or ".").resolve() != REPOSITORY_ROOT]


def create_supabase_client() -> Any:
    """Return the configured Supabase client."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required for storage")
    _without_repository_supabase_package()
    from supabase import create_client

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
