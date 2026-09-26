"""Registration and auto-verification API tests."""

from __future__ import annotations

import httpx

# Test credentials — must match application.yaml users section.
DEMO_EMAIL = "admin@auth.demo"
DEMO_PASSWORD = "Admin-Pass-123!"


async def test_register_returns_verification_token(
    client: httpx.AsyncClient,
) -> None:
    """Registration should return a verification token when auto_send_verification is enabled."""
    response = await client.post(
        "/api/register",
        json={
            "name": "New User",
            "email": "new-user@auth.demo",
            "password": "New-User-Pass-1!",
            "confirm_password": "New-User-Pass-1!",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["ok"] is True
    assert "user" in body
    assert body["user"]["email"] == "new-user@auth.demo"
    assert "verification_token" in body


async def test_register_session_is_active(
    client: httpx.AsyncClient,
) -> None:
    """After registration, the session should be active."""
    response = await client.post(
        "/api/register",
        json={
            "name": "Session User",
            "email": "session-user@auth.demo",
            "password": "Session-User-Pass-1!",
            "confirm_password": "Session-User-Pass-1!",
        },
    )
    assert response.status_code == 201

    # The session should be active — check /api/me.
    me = await client.get("/api/me")
    assert me.status_code == 200
    assert me.json()["email"] == "session-user@auth.demo"


async def test_register_then_verify_email(
    client: httpx.AsyncClient,
) -> None:
    """Register a new user, get verification token, verify email."""
    # Register.
    register = await client.post(
        "/api/register",
        json={
            "name": "Verify User",
            "email": "verify-user@auth.demo",
            "password": "Verify-User-Pass-1!",
            "confirm_password": "Verify-User-Pass-1!",
        },
    )
    assert register.status_code == 201
    token = register.json()["verification_token"]

    # Verify email with the token.
    verify = await client.post(
        "/api/verify-email",
        json={"token": token},
    )
    assert verify.status_code == 200
    assert verify.json()["ok"] is True


async def test_register_duplicate_email_fails(
    client: httpx.AsyncClient,
) -> None:
    """Registering with an existing email should fail."""
    response = await client.post(
        "/api/register",
        json={
            "name": "Admin Again",
            "email": DEMO_EMAIL,
            "password": "Admin-Pass-123!",
            "confirm_password": "Admin-Pass-123!",
        },
    )
    assert response.status_code == 409


async def test_register_password_mismatch_fails(
    client: httpx.AsyncClient,
) -> None:
    """Registering with mismatched passwords should fail."""
    response = await client.post(
        "/api/register",
        json={
            "name": "Mismatch User",
            "email": "mismatch@auth.demo",
            "password": "One-Pass-1!",
            "confirm_password": "Different-Pass-1!",
        },
    )
    assert response.status_code in (400, 422)


async def test_register_weak_password_fails(
    client: httpx.AsyncClient,
) -> None:
    """Registering with a weak password should fail."""
    response = await client.post(
        "/api/register",
        json={
            "name": "Weak User",
            "email": "weak@auth.demo",
            "password": "weak",
            "confirm_password": "weak",
        },
    )
    assert response.status_code in (400, 422)
