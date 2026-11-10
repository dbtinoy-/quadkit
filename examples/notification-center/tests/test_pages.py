"""Browser surface smoke tests."""

from __future__ import annotations

import httpx


async def test_console_explains_mailer_and_inbox(client: httpx.AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    assert "Notification Center" in response.text
    assert "Send an email" in response.text
    assert "Inbox" in response.text


async def test_static_assets(client: httpx.AsyncClient) -> None:
    assert (await client.get("/static/style.css")).status_code == 200
    assert (await client.get("/static/app.js")).status_code == 200
    assert (await client.get("/static/logo.png")).status_code == 200
    assert (await client.get("/static/icon.png")).status_code == 200
