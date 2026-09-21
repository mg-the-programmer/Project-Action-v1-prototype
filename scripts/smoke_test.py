"""Insert an entry into Supabase and verify that it can be retrieved by ID."""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]

# The repository's Supabase CLI directory is also named ``supabase``. Remove
# the repository root from import lookup so this resolves the installed client.
sys.path = [
    path for path in sys.path if Path(path or ".").resolve() != REPOSITORY_ROOT
]

from supabase import Client, create_client


def load_environment_file(path: Path) -> None:
    """Load unset environment variables from a simple KEY=VALUE .env file."""
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def create_supabase_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_KEY are required. Copy .env.example to .env "
            "and set both values."
        )
    return create_client(url, key)


def main() -> int:
    load_environment_file(REPOSITORY_ROOT / ".env")
    client = create_supabase_client()
    expected_content = "Personal KB smoke test entry"

    inserted = (
        client.table("entries")
        .insert({"content": expected_content, "source_type": "notion_note"})
        .select("id, content, source_type")
        .execute()
    )
    if not inserted.data:
        raise RuntimeError("Supabase did not return the inserted entry.")

    entry_id = inserted.data[0]["id"]
    retrieved = (
        client.table("entries")
        .select("id, content, source_type")
        .eq("id", entry_id)
        .single()
        .execute()
    )
    if retrieved.data != {
        "id": entry_id,
        "content": expected_content,
        "source_type": "notion_note",
    }:
        raise RuntimeError("Retrieved entry did not match the inserted entry.")

    print(f"Smoke test passed: inserted and retrieved entry {entry_id}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Smoke test failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
