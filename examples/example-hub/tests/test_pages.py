"""Smoke tests for the demo hub page routes.

Verifies the hub console serves HTML with expected structure,
static assets load correctly, and the Quadkit branding is present.
"""

from __future__ import annotations

import httpx

async def test_root_serves_hub(client: httpx.AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Quadkit Live Demos" in response.text

    response = await client.get("/")

    assert response.status_code == 200

async def test_hub_has_light_theme(client: httpx.AsyncClient) -> None:
    """Color tokens live in the shared tokens.css (docs-aligned brand
    palette), not in the hub's own style.css — see examples/CONSISTENCY.md."""
    tokens = await client.get("/static/tokens.css")

    assert tokens.status_code == 200
    assert "--bg: #f5f5f5;" in tokens.text
    assert '[data-theme="dark"]' in tokens.text
    # The brand accent is the identical lime in both light and dark palettes.
    assert tokens.text.count("--accent: #c8ff00;") == 2

async def test_hub_has_footer(client: httpx.AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert "footer" in response.text
    assert "quadkit.dev" in response.text

async def test_hub_has_filter_buttons(client: httpx.AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert 'data-f="all"' in response.text
    assert 'data-f="standard"' in response.text
    assert 'data-f="multi-module"' in response.text

async def test_hub_has_modal(client: httpx.AsyncClient) -> None:
    response = await client.get("/")

    assert response.status_code == 200
    assert "modal-overlay" in response.text
    assert "modal-title" in response.text

async def test_static_assets_served(client: httpx.AsyncClient) -> None:
    css = await client.get("/static/style.css")
    js = await client.get("/static/app.js")

    assert css.status_code == 200
    assert "text/css" in css.headers["content-type"]
    assert js.status_code == 200
    assert "javascript" in js.headers["content-type"]

async def test_api_status_returns_json(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/status")

    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]
    data = response.json()
    assert "services" in data
    assert len(data["services"]) > 0

async def test_api_status_has_required_fields(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/status")
    data = response.json()

    for svc in data["services"]:
        assert "slug" in svc
        assert "name" in svc
        assert "status" in svc
        assert "blurb" in svc
        assert svc["status"] in ("up", "down")
