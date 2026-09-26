"""End-to-end MFA flow tests: challenge, backup codes, enroll, disable."""

from __future__ import annotations

import time

import httpx
import pytest
from starlette.applications import Starlette

from quadkit.auth.authn.mfa import DEFAULT_TOTP_PERIOD, generate_totp_code
from quadkit.auth.authn.user_service import UserService

# Test credentials — must match application.yaml auth.users
PLAIN_EMAIL = "plain@mfa.demo"
MFA_EMAIL = "mfa@mfa.demo"
DEMO_PASSWORD = "Demo-Password-1"

PLAIN = {"email": PLAIN_EMAIL, "password": DEMO_PASSWORD}
MFA_USER = {"email": MFA_EMAIL, "password": DEMO_PASSWORD}


def second_browser(app: Starlette) -> httpx.AsyncClient:
    """An independent browser (own cookie jar) over the same running app."""
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    )


async def current_secret(app: Starlette, email: str) -> str:
    """Read the enrolled TOTP secret back out of the user's profile."""
    users = await app.container.resolve(UserService)
    user = await users.user_store.get_user_by_email(email)
    assert user is not None
    return user.profile["mfa"]["secret"]


async def code_for(app: Starlette, email: str) -> str:
    """Compute the current valid TOTP for a user."""
    secret = await current_secret(app, email)
    return generate_totp_code(secret)


async def generate_code_for_offset(
    app: Starlette,
    email: str,
    *,
    offset_steps: int,
) -> str:
    """Compute the TOTP for a time `offset_steps` periods away from now."""
    secret = await current_secret(app, email)
    return generate_totp_code(
        secret,
        for_time=int(time.time()) - offset_steps * DEFAULT_TOTP_PERIOD,
    )


async def login(client: httpx.AsyncClient, creds: dict[str, str]) -> httpx.Response:
    return await client.post("/api/login", json=creds)


@pytest.fixture
async def authed_plain(
    app: Starlette, client: httpx.AsyncClient
) -> httpx.AsyncClient:
    """Log in as the plain user and return the authenticated client."""
    await client.post("/api/login", json=PLAIN)
    return client


async def test_plain_user_skips_challenge(client: httpx.AsyncClient) -> None:
    response = await login(client, PLAIN)

    assert response.status_code == 200
    assert response.json()["mfa_required"] is False
    assert "session_id" in response.cookies
    me = await client.get("/api/me")
    assert me.status_code == 200


async def test_mfa_login_issues_pending_challenge(client: httpx.AsyncClient) -> None:
    response = await login(client, MFA_USER)

    assert response.status_code == 200
    assert response.json()["mfa_required"] is True
    assert "mfa_pending" in response.cookies
    # No real session yet.
    me = await client.get("/api/me")
    assert me.status_code == 401


async def test_valid_code_upgrades_to_full_session(
    client: httpx.AsyncClient, app: Starlette
) -> None:
    await login(client, MFA_USER)
    code = await code_for(app, MFA_EMAIL)

    response = await client.post("/api/mfa/challenge", json={"code": code})

    assert response.status_code == 200
    assert "session_id" in response.cookies
    me = await client.get("/api/me")
    assert me.status_code == 200


async def test_wrong_code_attempts_are_capped(client: httpx.AsyncClient) -> None:
    await login(client, MFA_USER)

    statuses: list[tuple[int, str]] = []
    for _ in range(4):
        response = await client.post("/api/mfa/challenge", json={"code": "000000"})
        statuses.append((response.status_code, response.json().get("detail", "")))

    assert all(status == 401 for status, _ in statuses)
    assert "too many attempts" in statuses[2][1]
    assert "no pending challenge" in statuses[3][1]


async def test_enroll_returns_provisioning_material_once(
    authed_plain: httpx.AsyncClient,
) -> None:
    response = await authed_plain.post("/api/mfa/enroll")

    assert response.status_code == 200
    body = response.json()
    assert body["provisioning_uri"].startswith("otpauth://totp/")
    assert len(body["backup_codes"]) >= 8


async def test_backup_code_works_exactly_once(
    client: httpx.AsyncClient, app: Starlette
) -> None:
    await client.post("/api/login", json=PLAIN)
    enroll = await client.post("/api/mfa/enroll")
    backup_code = enroll.json()["backup_codes"][0]

    async def challenge_with(browser: httpx.AsyncClient) -> httpx.Response:
        await browser.post("/api/login", json=PLAIN)
        return await browser.post("/api/mfa/challenge", json={"code": backup_code})

    first = second_browser(app)
    ok = await challenge_with(first)
    assert ok.status_code == 200

    second = second_browser(app)
    replay = await challenge_with(second)
    assert replay.status_code == 401
    await first.aclose()
    await second.aclose()


async def test_disable_requires_correct_password(
    authed_plain: httpx.AsyncClient,
) -> None:
    await authed_plain.post("/api/mfa/enroll")

    wrong = await authed_plain.post(
        "/api/mfa/disable", json={"password": "nope"}
    )
    assert wrong.status_code == 401

    status = await authed_plain.get("/api/mfa/status")
    assert status.json()["enabled"] is True

    right = await authed_plain.post(
        "/api/mfa/disable", json={"password": PLAIN["password"]}
    )
    assert right.status_code == 200
    status = await authed_plain.get("/api/mfa/status")
    assert status.json()["enabled"] is False


async def test_stale_totp_code_is_rejected(
    client: httpx.AsyncClient, app: Starlette
) -> None:
    """A code from a long-expired time step fails even within the +/-1 window."""
    await login(client, MFA_USER)
    stale = await generate_code_for_offset(app, MFA_EMAIL, offset_steps=5)

    response = await client.post("/api/mfa/challenge", json={"code": stale})
    assert response.status_code == 401
    assert "invalid code" in response.json()["detail"]


async def test_challenge_without_pending_cookie_is_401(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/api/mfa/challenge", json={"code": "123456"})
    assert response.status_code == 401
    assert "no pending challenge" in response.json()["detail"]


async def test_double_enroll_conflicts(authed_plain: httpx.AsyncClient) -> None:
    await authed_plain.post("/api/mfa/enroll")
    again = await authed_plain.post("/api/mfa/enroll")
    assert again.status_code == 409


async def test_me_requires_session(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/me")).status_code == 401


async def test_mfa_status_reports_backup_codes(
    client: httpx.AsyncClient, app: Starlette
) -> None:
    await client.post("/api/login", json=PLAIN)
    before = (await client.get("/api/mfa/status")).json()
    assert before["enabled"] is False

    enroll = await client.post("/api/mfa/enroll")
    codes = enroll.json()["backup_codes"]

    after = (await client.get("/api/mfa/status")).json()
    assert after["enabled"] is True
    assert after["backup_codes_left"] == len(codes)
