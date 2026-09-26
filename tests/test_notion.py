from __future__ import annotations

from types import SimpleNamespace

from shared.notion import _page_id_from_mcp_response


def test_extracts_a_page_id_from_structured_mcp_content() -> None:
    response = SimpleNamespace(structuredContent={"pages": [{"id": "page-1"}]}, content=[])

    assert _page_id_from_mcp_response(response) == "page-1"


def test_extracts_a_page_id_from_a_notion_page_url() -> None:
    response = SimpleNamespace(
        structuredContent=None,
        content=[SimpleNamespace(text="Created https://www.notion.so/49d05189bf8e4998a87a2951c48e5ea4")],
    )

    assert _page_id_from_mcp_response(response) == "49d05189bf8e4998a87a2951c48e5ea4"
