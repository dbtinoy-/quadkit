"""Exercise the real auth-tokens composition root through HTTP."""

from __future__ import annotations

import httpx


async def _login(client: httpx.AsyncClient, username: str = "ada", password: str = "wonderland") -> httpx.Response:
    return await client.post("/session", json={"username": username, "password": password})


async def test_login_issues_token_and_me_returns_claims(client: httpx.AsyncClient) -> None:
    session = await _login(client)
    assert session.status_code == 201
    token = session.json()["token"]
    assert session.json()["type"] == "bearer"

    me = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json() == {"sub": "ada", "roles": ["admin"]}


async def test_me_without_token_is_problem_detail_401(client: httpx.AsyncClient) -> None:
    me = await client.get("/me")
    assert me.status_code == 401
    body = me.json()
    assert body["status"] == 401
    assert "bearer" in body["detail"].lower()


async def test_wrong_password_is_401_and_tampered_token_rejected(client: httpx.AsyncClient) -> None:
    bad = await _login(client, password="nope")
    assert bad.status_code == 401

    session = await _login(client)
    token = session.json()["token"]
    forged = token[:-1] + ("A" if token[-1] != "A" else "B")
    me = await client.get("/me", headers={"Authorization": f"Bearer {forged}"})
    assert me.status_code == 401


async def test_index_describes_the_demo(client: httpx.AsyncClient) -> None:
    """The hub mounts this demo at ``/examples/<slug>/`` — ``/`` must answer."""
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["demo"] == "auth-tokens"
    assert isinstance(body["endpoints"], list) and body["endpoints"]
