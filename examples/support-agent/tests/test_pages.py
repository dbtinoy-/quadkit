"""Smoke tests for the support agent console page routes."""

from __future__ import annotations

from quadkit.contracts.constants import DOCS_BASE_URL

import httpx

async def test_root_serves_console(client: httpx.AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Support Agent Console" in response.text
    assert 'data-scenario="happy"' in response.text
    assert 'data-scenario="multi_tool"' in response.text
    assert 'data-scenario="failure"' in response.text

    response = await client.get("/")

    assert response.status_code == 200

async def test_page_has_light_theme(client: httpx.AsyncClient) -> None:
    css = await client.get("/static/tokens.css")

    assert css.status_code == 200
    assert "--bg: #f5f5f5;" in css.text and "--accent: #c8ff00;" in css.text

async def test_page_has_footer(client: httpx.AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert "demo-footer" in response.text
    assert DOCS_BASE_URL in response.text

async def test_static_assets_served(client: httpx.AsyncClient) -> None:
    css = await client.get("/static/style.css")
    js = await client.get("/static/app.js")

    assert css.status_code == 200
    assert "text/css" in css.headers["content-type"]
    assert js.status_code == 200
    assert "javascript" in js.headers["content-type"]
