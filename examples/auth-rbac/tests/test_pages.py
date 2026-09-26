"""Page controller tests for the auth-rbac demo."""

from __future__ import annotations

from quadkit.contracts.constants import DOCS_BASE_URL

import httpx
from starlette.applications import Starlette

from quadkit.config.main import QuadkitConfig
from quadkit.web.config import WebConfig

async def test_server_backend_config(app: Starlette) -> None:
    """Verify web.server.backend is loaded from application.yaml."""
    config = QuadkitConfig.from_yaml()
    web = config.get_section("web", WebConfig)
    assert web.server.backend == "uvicorn"

async def test_login_renders(client: httpx.AsyncClient) -> None:
    r = await client.get("/login", follow_redirects=False)
    assert r.status_code == 200
    assert "persona" in r.text.lower()

async def test_matrix_renders(client: httpx.AsyncClient) -> None:
    r = await client.get("/matrix", follow_redirects=False)
    assert r.status_code == 200
    assert "Permission matrix" in r.text

async def test_index_redirects(client: httpx.AsyncClient) -> None:
    r = await client.get("/", follow_redirects=False)
    assert r.status_code == 307

    r = await client.get("/login", follow_redirects=False)

    r = await client.get("/matrix", follow_redirects=False)

async def test_login_has_light_theme(client: httpx.AsyncClient) -> None:
    css = await client.get("/static/tokens.css")
    assert css.status_code == 200
    assert "--bg: #f5f5f5;" in css.text and "--accent: #c8ff00;" in css.text

async def test_login_has_footer(client: httpx.AsyncClient) -> None:
    r = await client.get("/login", follow_redirects=False)
    assert "demo-footer" in r.text
    assert DOCS_BASE_URL in r.text

async def test_matrix_has_footer(client: httpx.AsyncClient) -> None:
    r = await client.get("/matrix", follow_redirects=False)
    assert "demo-footer" in r.text

async def test_css_returns(client: httpx.AsyncClient) -> None:
    r = await client.get("/static/style.css")
    assert r.status_code == 200

