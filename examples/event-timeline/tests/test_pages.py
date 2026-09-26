"""Browser surface smoke tests."""

from __future__ import annotations

import httpx


async def test_console_explains_event_controls(client: httpx.AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert "Events Timeline · Quadkit" in response.text
    assert "Simulate failure" in response.text
    assert "Replay history" in response.text
    assert "EventBusProtocol" in response.text


async def test_static_assets(client: httpx.AsyncClient) -> None:
    assert (await client.get("/static/style.css")).status_code == 200
    assert (await client.get("/static/app.js")).status_code == 200
