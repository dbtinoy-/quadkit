"""Password reset and account verification API tests."""

from __future__ import annotations

import httpx

# Test credentials — must match application.yaml users section.
DEMO_EMAIL = "admin@auth.demo"
DEMO_PASSWORD = "Admin-Pass-123!"


async def test_forgot_password_returns_token(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/forgot-password",
        json={"email": DEMO_EMAIL},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert "reset_token" in body


async def test_forgot_password_unknown_email_returns_200(
    client: httpx.AsyncClient,
) -> None:
    """Returns 200 even for unknown emails to prevent enumeration."""
    response = await client.post(
        "/api/forgot-password",
        json={"email": "unknown@example.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True


async def test_reset_password_with_valid_token(
    client: httpx.AsyncClient,
) -> None:
    # Request a reset token.
    forgot = await client.post(
        "/api/forgot-password",
        json={"email": DEMO_EMAIL},
    )
    token = forgot.json()["reset_token"]

    # Reset the password.
    reset = await client.post(
        "/api/reset-password",
        json={"token": token, "new_password": "New-Reset-Pass-1"},
    )
    assert reset.status_code == 200
    assert reset.json()["ok"] is True

    # Login with the new password.
    login = await client.post(
        "/api/login",
        json={"email": DEMO_EMAIL, "password": "New-Reset-Pass-1"},
    )
    assert login.status_code == 200

    # Restore the original password.
    forgot2 = await client.post(
        "/api/forgot-password",
        json={"email": DEMO_EMAIL},
    )
    token2 = forgot2.json()["reset_token"]
    await client.post(
        "/api/reset-password",
        json={"token": token2, "new_password": DEMO_PASSWORD},
    )


async def test_reset_password_with_invalid_token(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/reset-password",
        json={"token": "invalid-token-abc", "new_password": "New-Pass-1"},
    )
    assert response.status_code == 400


async def test_send_and_verify_email(client: httpx.AsyncClient) -> None:
    # Login first.
    await client.post(
        "/api/login",
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )

    # Send verification.
    send = await client.post("/api/send-verification")
    assert send.status_code == 200
    token = send.json()["verification_token"]

    # Verify with the token.
    verify = await client.post(
        "/api/verify-email",
        json={"token": token},
    )
    assert verify.status_code == 200
    assert verify.json()["ok"] is True


async def test_verify_email_with_invalid_token(
    client: httpx.AsyncClient,
) -> None:
    # Login first.
    await client.post(
        "/api/login",
        json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )

    response = await client.post(
        "/api/verify-email",
        json={"token": "invalid-token-abc"},
    )
    assert response.status_code == 401


async def test_send_verification_requires_auth(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/api/send-verification")
    assert response.status_code == 401


async def test_verify_email_requires_auth(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/verify-email",
        json={"token": "some-token"},
    )
    assert response.status_code == 401
