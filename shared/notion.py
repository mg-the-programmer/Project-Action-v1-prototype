"""Notion-MCP publishing boundary for the curated personal-KB action surface."""
from __future__ import annotations

import os
import re
from collections.abc import Mapping
from contextlib import AsyncExitStack
from typing import Any, Protocol


class NotionPagePublisher(Protocol):
    """Create one Notion page and return its Notion page id."""

    async def create_page(self, page: Mapping[str, Any]) -> str: ...


class NotionMcpPublisher:
    """Publish through a configured Notion MCP server, never Notion's REST API."""

    def __init__(self, *, url: str | None = None, data_source_id: str | None = None) -> None:
        self.url = url or os.environ.get("NOTION_MCP_URL")
        self.data_source_id = data_source_id or os.environ.get("NOTION_DATA_SOURCE_ID")
        if not self.url or not self.data_source_id:
            raise RuntimeError("NOTION_MCP_URL and NOTION_DATA_SOURCE_ID are required for Notion sync")

    async def create_page(self, page: Mapping[str, Any]) -> str:
        """Invoke Notion's MCP page-creation tool over configured Streamable HTTP."""
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        request = {"parent": {"type": "data_source_id", "data_source_id": self.data_source_id}, "pages": [dict(page)]}
        async with AsyncExitStack() as stack:
            read, write, _ = await stack.enter_async_context(streamablehttp_client(self.url))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            response = await session.call_tool("notion_notion_create_pages", request)
        return _page_id_from_mcp_response(response)


def _page_id_from_mcp_response(response: Any) -> str:
    """Extract the returned page id without binding callers to an MCP SDK shape."""
    structured = getattr(response, "structuredContent", None)
    if isinstance(structured, Mapping):
        for key in ("page_id", "id"):
            value = structured.get(key)
            if isinstance(value, str) and value:
                return value
        pages = structured.get("pages")
        if isinstance(pages, list) and pages and isinstance(pages[0], Mapping):
            value = pages[0].get("id")
            if isinstance(value, str) and value:
                return value
    for item in getattr(response, "content", []) or []:
        text = getattr(item, "text", None)
        if not isinstance(text, str):
            continue
        match = re.search(r"(?:notion\.so/|page[_ -]id[=: ]+)([0-9a-f]{32}|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})", text, re.IGNORECASE)
        if match:
            return match.group(1)
    raise RuntimeError("Notion MCP created a page but did not return a page id")
