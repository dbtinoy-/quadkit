"""Browser surface smoke tests."""

from __future__ import annotations

import httpx


async def test_console_explains_approval_flow(client: httpx.AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert "Approval Flow" in response.text
    assert "ApprovalChain preview" in response.text
    assert "Transition history" in response.text


async def test_static_assets(client: httpx.AsyncClient) -> None:
    assert (await client.get("/static/style.css")).status_code == 200
    assert (await client.get("/static/app.js")).status_code == 200
