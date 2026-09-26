"""Page controller tests."""

from __future__ import annotations

from quadkit.contracts.constants import DOCS_BASE_URL

import httpx

async def test_console_renders(client: httpx.AsyncClient) -> None:
    r = await client.get("/")
    assert r.status_code == 200
    assert "Quadkit" in r.text

async def test_console_has_nav(client: httpx.AsyncClient) -> None:
    r = await client.get("/")
    assert "demo-nav" in r.text
    assert "nav-brand" in r.text

async def test_console_has_light_theme(client: httpx.AsyncClient) -> None:
    css = await client.get("/static/tokens.css")
    assert css.status_code == 200
    assert "--bg: #f5f5f5;" in css.text and "--accent: #c8ff00;" in css.text

async def test_console_has_footer(client: httpx.AsyncClient) -> None:
    r = await client.get("/")
    assert "demo-footer" in r.text
    assert DOCS_BASE_URL in r.text

async def test_css_returns(client: httpx.AsyncClient) -> None:
    r = await client.get("/static/style.css")
    assert r.status_code == 200

async def test_js_returns(client: httpx.AsyncClient) -> None:
    r = await client.get("/static/app.js")
    assert r.status_code == 200
