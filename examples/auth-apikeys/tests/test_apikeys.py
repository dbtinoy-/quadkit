"""End-to-end API-key flow tests: issue, machine auth, revoke, expiry."""
# E2E tests — boot the real app, exercise HTTP endpoints,
# verify full request/response cycle. Uses httpx.AsyncClient with
# ASGITransport for in-process testing (no server needed).

from __future__ import annotations

import httpx
import pytest
from starlette.applications import Starlette

# Test credentials — must match application.yaml auth.users[0]
DEMO_EMAIL = "admin@keys.demo"
DEMO_PASSWORD = "Demo-Password-1"

EXPIRED_RAW = "sk_live_expired0000000000000000000000000000"


def second_browser(app: Starlette) -> httpx.AsyncClient:
    """An independent browser (own cookie jar) over the same running app."""
    # Independent session — second_browser creates a fresh
    # httpx client with its own cookies, simulating a separate machine
    # making API-key-only requests (no session cookies).
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    )


@pytest.fixture
async def logged_in(client: httpx.AsyncClient) -> httpx.AsyncClient:
    # logged_in fixture — logs in once, reuses the
    # authenticated client across tests. Session cookie is stored
    # in the client's cookie jar.
    response = await client.post(
        "/api/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return client


async def test_login_sets_session(logged_in: httpx.AsyncClient) -> None:
    assert "session_id" in logged_in.cookies


async def test_create_returns_raw_key_once(logged_in: httpx.AsyncClient) -> None:
    created = await logged_in.post(
        "/api/keys/create",
        json={"name": "ci-key", "scopes": ["read"]},
    )

    assert created.status_code == 201
    body = created.json()
    assert body["raw_key"].startswith("sk_live")
    assert body["prefix"] in body["raw_key"]


async def test_machine_me_with_valid_key(
    app: Starlette, logged_in: httpx.AsyncClient
) -> None:
    created = await logged_in.post(
        "/api/keys/create", json={"name": "bot", "scopes": ["read"]}
    )
    raw_key = created.json()["raw_key"]

    machine = second_browser(app)
    response = await machine.get("/api/me", headers={"X-API-Key": raw_key})

    assert response.status_code == 200
    body = response.json()
    assert body["scopes"] == ["read"]
    assert body["user_id"]
    await machine.aclose()


async def test_machine_me_without_key_is_401(
    app: Starlette,
) -> None:
    machine = second_browser(app)
    response = await machine.get("/api/me")
    assert response.status_code == 401
    await machine.aclose()


async def test_revoked_key_is_401(
    app: Starlette, logged_in: httpx.AsyncClient
) -> None:
    created = await logged_in.post(
        "/api/keys/create", json={"name": "short-lived", "scopes": ["read"]}
    )
    raw_key = created.json()["raw_key"]

    ok = await second_browser(app).get("/api/me", headers={"X-API-Key": raw_key})
    assert ok.status_code == 200

    keys = (await logged_in.get("/api/keys")).json()["keys"]
    target = next(k for k in keys if k["key_id"])
    revoked = await logged_in.post(f"/api/keys/{target['key_id']}/revoke")
    assert revoked.status_code == 200

    after = await second_browser(app).get(
        "/api/me", headers={"X-API-Key": raw_key}
    )
    assert after.status_code == 401


async def test_garbage_key_is_401(app: Starlette) -> None:
    machine = second_browser(app)
    response = await machine.get(
        "/api/me", headers={"X-API-Key": "sk_live_garbage"}
    )
    assert response.status_code == 401


async def test_management_requires_cookie(app: Starlette) -> None:
    anon = second_browser(app)

    listing = await anon.get("/api/keys")
    create = await anon.post("/api/keys/create", json={"name": "x"})

    assert listing.status_code == 401
    assert create.status_code == 401
    await anon.aclose()


async def test_revoked_key_cannot_revoke_again(
    app: Starlette, logged_in: httpx.AsyncClient
) -> None:
    created = await logged_in.post(
        "/api/keys/create", json={"name": "once", "scopes": ["read"]}
    )
    key_id = created.json()["key_id"]

    first = await logged_in.post(f"/api/keys/{key_id}/revoke")
    assert first.status_code == 200

    second = await logged_in.post(f"/api/keys/{key_id}/revoke")
    assert second.status_code == 404
    assert "unknown key" in second.json()["detail"]


async def test_revoke_unknown_key_is_404(
    logged_in: httpx.AsyncClient,
) -> None:
    response = await logged_in.post("/api/keys/nope/revoke")
    assert response.status_code == 404


async def test_created_key_appears_in_listing(
    app: Starlette, logged_in: httpx.AsyncClient
) -> None:
    created = await logged_in.post(
        "/api/keys/create",
        json={"name": "listed", "scopes": ["read", "write"]},
    )
    body = created.json()

    keys = (await logged_in.get("/api/keys")).json()["keys"]
    match = next(k for k in keys if k["key_id"] == body["key_id"])
    assert match["name"] == "listed"
    assert match["scopes"] == ["read", "write"]
    # the raw secret never appears in listings — only the prefix
    assert body["raw_key"].startswith(match["prefix"])
    assert "raw_key" not in match
    assert body["raw_key"] not in str(keys)


async def test_expired_seed_key_is_401(app: Starlette) -> None:
    machine = second_browser(app)
    response = await machine.get("/api/me", headers={"X-API-Key": EXPIRED_RAW})
    assert response.status_code == 401
    await machine.aclose()


async def test_login_bad_password_is_401(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/login", json={"email": DEMO_EMAIL, "password": "wrong"}
    )
    assert response.status_code == 401
