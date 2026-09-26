"""Shared HTTP request support for API smoke tests."""
from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import FastAPI


def asgi_request(app: FastAPI, method: str, url: str, **kwargs: Any) -> httpx.Response:
    """Send one observable request through a FastAPI ASGI application."""
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, url, **kwargs)

    return asyncio.run(send())
