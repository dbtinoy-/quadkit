"""Page controller tests for the auth-web demo."""

from __future__ import annotations

from quadkit.contracts.constants import DOCS_BASE_URL

import httpx

async def test_login_renders(client: httpx.AsyncClient) -> None:
    r = await client.get("/login", follow_redirects=False)
    assert r.status_code == 200
    assert "Log in" in r.text

async def test_register_renders(client: httpx.AsyncClient) -> None:
    r = await client.get("/register", follow_redirects=False)
    assert r.status_code == 200
    assert "Register" in r.text

async def test_profile_renders(client: httpx.AsyncClient) -> None:
    r = await client.get("/profile", follow_redirects=False)
    assert r.status_code == 200
    assert "Profile" in r.text

async def test_password_renders(client: httpx.AsyncClient) -> None:
    r = await client.get("/password", follow_redirects=False)
    assert r.status_code == 200
    assert "Change password" in r.text

async def test_index_redirects(client: httpx.AsyncClient) -> None:
    r = await client.get("/", follow_redirects=False)
    assert r.status_code == 307

    r = await client.get("/login", follow_redirects=False)

async def test_login_has_light_theme(client: httpx.AsyncClient) -> None:
    css = await client.get("/static/tokens.css")
    assert css.status_code == 200
    assert "--bg: #f5f5f5;" in css.text and "--accent: #c8ff00;" in css.text

async def test_login_has_footer(client: httpx.AsyncClient) -> None:
    r = await client.get("/login", follow_redirects=False)
    assert "demo-footer" in r.text
    assert DOCS_BASE_URL in r.text

async def test_css_returns(client: httpx.AsyncClient) -> None:
    r = await client.get("/static/style.css")
    assert r.status_code == 200
    assert "text/css" in r.headers["content-type"]

    r = await client.get("/profile", follow_redirects=False)

async def test_profile_has_footer(client: httpx.AsyncClient) -> None:
    r = await client.get("/profile", follow_redirects=False)
    assert "demo-footer" in r.text
