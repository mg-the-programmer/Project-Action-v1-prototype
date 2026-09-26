"""Export rated retrieval logs to a portable LangSmith-compatible dataset."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Protocol

from scripts.transcribe import REPOSITORY_ROOT, load_environment_file
from shared.clients import create_supabase_client

DEFAULT_OUTPUT = REPOSITORY_ROOT / "eval" / "pairs.json"


class EvaluationDatabase(Protocol):
    """The read-only Supabase surface needed to export feedback."""

    def table(self, table_name: str) -> Any: ...


def rated_logs(client: EvaluationDatabase | None = None) -> list[dict[str, Any]]:
    """Read rated retrieval logs in their stable creation order."""
    database = client or create_supabase_client()
    return (
        database.table("retrieval_logs")
        .select("id,query,results,rating,comment,created_at")
        .not_.is_("rating", "null")
        .order("created_at")
        .execute()
        .data
        or []
    )


def dataset_pairs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map rated logs to the agreed eval-pair shape without inventing labels.

    A rating says whether a retrieved set was useful; it does not identify which
    entry was expected.  ``expected_entry_ids`` therefore remains empty until a
    future explicit relevance-label field is added, rather than fabricating a
    ground truth from the returned results.
    """
    pairs: list[dict[str, Any]] = []
    for row in rows:
        query, rating = row.get("query"), row.get("rating")
        results = row.get("results") if isinstance(row.get("results"), list) else []
        if not isinstance(query, str) or isinstance(rating, bool) or not isinstance(rating, int):
            raise ValueError("Rated retrieval logs must contain a text query and integer rating")
        pairs.append({
            "query": query,
            "expected_entry_ids": [],
            "actual_results": results,
            "rating": rating,
            "comment": row.get("comment") if isinstance(row.get("comment"), str) else "",
        })
    return pairs


def write_pairs(output: Path, pairs: list[dict[str, Any]]) -> Path:
    """Write pairs as readable JSON for LangSmith import or API upload."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(pairs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def push_pairs_to_langsmith(pairs: list[dict[str, Any]], *, dataset_name: str) -> int:
    """Create or append examples to a configured LangSmith dataset.

    LangSmith authentication is supplied exclusively through environment
    variables (not command-line arguments).  The caller must configure
    ``LANGSMITH_API_KEY`` and ``LANGSMITH_PROJECT`` before requesting a push.
    """
    if not os.environ.get("LANGSMITH_API_KEY") or not os.environ.get("LANGSMITH_PROJECT"):
        raise RuntimeError("LANGSMITH_API_KEY and LANGSMITH_PROJECT are required to push eval pairs")
    try:
        from langsmith import Client
    except ImportError as error:
        raise RuntimeError("Install the project's langsmith dependency before pushing eval pairs") from error
    client = Client()
    try:
        dataset = client.read_dataset(dataset_name=dataset_name)
    except Exception as error:
        if error.__class__.__name__ not in {"LangSmithNotFoundError", "HTTPError"}:
            raise
        dataset = client.create_dataset(dataset_name=dataset_name, description="Personal KB rated retrieval pairs")
    for pair in pairs:
        client.create_example(
            inputs={"query": pair["query"]},
            outputs={key: value for key, value in pair.items() if key != "query"},
            dataset_id=dataset.id,
        )
    return len(pairs)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export rated retrieval logs to eval/pairs.json.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--push", action="store_true", help="Push the exported pairs to configured LangSmith")
    parser.add_argument(
        "--dataset",
        help="LangSmith dataset name (defaults to configured LANGSMITH_PROJECT when pushing)",
    )
    arguments = parser.parse_args()
    load_environment_file(REPOSITORY_ROOT / ".env")
    try:
        pairs = dataset_pairs(rated_logs())
        output = write_pairs(arguments.output, pairs)
        print(f"Wrote {len(pairs)} rated retrieval pairs to {output}")
        if arguments.push:
            dataset_name = arguments.dataset or os.environ.get("LANGSMITH_PROJECT", "")
            print(f"Pushed {push_pairs_to_langsmith(pairs, dataset_name=dataset_name)} pairs to LangSmith")
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Error: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
