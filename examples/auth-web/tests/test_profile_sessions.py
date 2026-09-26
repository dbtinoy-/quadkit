"""Profile, claims, sessions and password-change API tests."""

from __future__ import annotations

import httpx
import pytest

# Test credentials — must match application.yaml users section.
DEMO_EMAIL = "admin@auth.demo"
DEMO_PASSWORD = "Admin-Pass-123!"


def _second_browser(app) -> httpx.AsyncClient:
    """An independent browser (own cookie jar) over the same running app."""
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    )


@pytest.fixture
async def authed(client: httpx.AsyncClient) -> httpx.AsyncClient:
    await client.post(
        "/api/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
    )
    return client


async def test_profile_returns_claims_and_sessions(authed: httpx.AsyncClient) -> None:
    response = await authed.get("/api/profile")

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == DEMO_EMAIL
    assert "admin" in body["claims"]["roles"]
    assert "*" in body["claims"]["permissions"]
    assert body["token_preview"].endswith("…")
    assert len(body["sessions"]) >= 1


async def test_revoke_second_session_kills_it(
    app, authed: httpx.AsyncClient
) -> None:
    second = _second_browser(app)
    await second.post(
        "/api/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
    )
    second_session_id = second.cookies.get("session_id")
    assert second_session_id

    profile = await authed.get("/api/profile")
    session_ids = [row["session_id"] for row in profile.json()["sessions"]]
    assert second_session_id in session_ids

    revoke = await authed.post(f"/api/sessions/{second_session_id}/revoke")
    assert revoke.status_code == 200

    after = await second.get("/api/me")
    assert after.status_code == 401
    await second.aclose()


async def test_revoke_unknown_session_404(authed: httpx.AsyncClient) -> None:
    response = await authed.post("/api/sessions/does-not-exist/revoke")
    assert response.status_code == 404


async def test_change_password_wrong_current_is_error(
    authed: httpx.AsyncClient,
) -> None:
    response = await authed.post(
        "/api/profile/password",
        json={
            "current_password": "nope",
            "new_password": "Brand-New-Pass-1",
            "confirm_password": "Brand-New-Pass-1",
        },
    )
    # wrong current password → InvalidCredentialsError → 401
    assert response.status_code == 401


async def test_change_password_updates_and_relogin_works(
    app, authed: httpx.AsyncClient
) -> None:
    changed = await authed.post(
        "/api/profile/password",
        json={
            "current_password": DEMO_PASSWORD,
            "new_password": "Brand-New-Pass-1",
            "confirm_password": "Brand-New-Pass-1",
        },
    )
    assert changed.status_code == 200

    fresh = _second_browser(app)
    relogin = await fresh.post(
        "/api/login", json={"email": DEMO_EMAIL, "password": "Brand-New-Pass-1"}
    )
    assert relogin.status_code == 200

    # Restore the demo password so later tests keep working.
    me = await fresh.get("/api/me")
    me.json()["user_id"]  # identity confirmed
    restore = await fresh.post(
        "/api/profile/password",
        json={
            "current_password": "Brand-New-Pass-1",
            "new_password": DEMO_PASSWORD,
            "confirm_password": DEMO_PASSWORD,
        },
    )
    assert restore.status_code == 200
    await fresh.aclose()
