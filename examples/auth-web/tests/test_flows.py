"""End-to-end API flow tests against the booted app."""

from __future__ import annotations

import httpx


# Test credentials — must match application.yaml users section.
DEMO_EMAIL = "admin@auth.demo"
DEMO_PASSWORD = "Admin-Pass-123!"


async def login(client: httpx.AsyncClient) -> httpx.Response:
    return await client.post(
        "/api/login",
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )


async def test_root_redirects_anonymous_to_login(client: httpx.AsyncClient) -> None:
    response = await client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"] == "/login"


async def test_login_wrong_password_returns_401(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/login",
        json={"email": DEMO_EMAIL, "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]


async def test_login_success_sets_cookie_and_identity(
    client: httpx.AsyncClient,
) -> None:
    response = await login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == DEMO_EMAIL
    assert "session_id" in response.cookies


async def test_me_requires_session(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/me")
    assert response.status_code == 401


async def test_me_returns_identity_after_login(client: httpx.AsyncClient) -> None:
    await login(client)

    response = await client.get("/api/me")

    assert response.status_code == 200
    assert response.json()["email"] == DEMO_EMAIL


async def test_logout_clears_cookie(client: httpx.AsyncClient) -> None:
    await login(client)

    response = await client.post("/api/logout")

    assert response.status_code == 200
    me = await client.get("/api/me")
    assert me.status_code == 401


async def test_register_creates_account_and_logs_in(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/register",
        json={
            "name": "New User",
            "email": "new@auth.demo",
            "password": "Another-Demo-Pass-1",
            "confirm_password": "Another-Demo-Pass-1",
        },
    )

    assert response.status_code == 201
    me = await client.get("/api/me")
    assert me.json()["email"] == "new@auth.demo"


async def test_register_duplicate_email_returns_409(
    client: httpx.AsyncClient,
) -> None:
    await login(client)  # ensure DEMO user exists

    response = await client.post(
        "/api/register",
        json={
            "name": "Dup User",
            "email": DEMO_EMAIL,
            "password": DEMO_PASSWORD,
            "confirm_password": DEMO_PASSWORD,
        },
    )

    assert response.status_code in (400, 409)


async def test_password_mismatch_is_rejected(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/register",
        json={
            "name": "Mismatch",
            "email": "mismatch@auth.demo",
            "password": "Some-Pass-123",
            "confirm_password": "Different-Pass-123",
        },
    )
    assert response.status_code == 400


async def test_account_lockout_after_repeated_failures(
    client: httpx.AsyncClient,
) -> None:
    for _ in range(5):
        await client.post(
            "/api/login",
            json={"email": DEMO_EMAIL, "password": "wrong-password"},
        )
    response = await login(client)
    # Correct password must NOT bypass an active lockout.
    assert response.status_code == 401
    assert "locked" in response.json()["detail"].lower()
