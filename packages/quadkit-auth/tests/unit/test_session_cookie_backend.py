"""Unit tests for SessionCookieBackend.

All dependencies are faked at the contract boundary — no real database or
HTTP framework required.  Each test is fully independent with no shared
mutable state.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.auth.session.cookie_backend import SessionCookieBackend

# ---------------------------------------------------------------------------
# Helpers / fakes
# ---------------------------------------------------------------------------


def _make_session_repo(
    *,
    find_active_result: dict[str, Any] | None = None,
) -> MagicMock:
    """Return a mock SessionRepositoryProtocol with sane defaults."""
    repo = MagicMock()
    repo.find_active = AsyncMock(return_value=find_active_result)
    repo.update_activity = AsyncMock(return_value=None)
    repo.insert = AsyncMock(return_value=None)
    repo.revoke = AsyncMock(return_value=None)
    return repo


def _make_user(user_id: str = "user-123") -> MagicMock:
    """Return a minimal AuthenticatedUserProtocol-compatible mock."""
    user = MagicMock()
    user.user_id = user_id
    return user


def _make_request(session_id: str | None = "sess-abc") -> MagicMock:
    """Return a request mock whose cookies contain *session_id*."""
    request = MagicMock()
    request.cookies = (
        {
            "session_id": session_id,
        }
        if session_id
        else {}
    )
    return request


def _make_response() -> MagicMock:
    response = MagicMock()
    response.set_cookie = MagicMock()
    response.delete_cookie = MagicMock()
    return response


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestSessionCookieBackendConstruction:
    def test_default_cookie_settings(self) -> None:
        repo = _make_session_repo()
        backend = SessionCookieBackend(
            session_repository=repo,
            user_fetcher=AsyncMock(),
        )
        assert backend._cookie_name == "session_id"
        assert backend._secure is True
        assert backend._http_only is True
        assert backend._same_site == "lax"

    def test_custom_cookie_settings(self) -> None:
        repo = _make_session_repo()
        backend = SessionCookieBackend(
            session_repository=repo,
            user_fetcher=AsyncMock(),
            cookie_name="admin_session",
            secure=False,
            http_only=False,
            same_site="strict",
        )
        assert backend._cookie_name == "admin_session"
        assert backend._secure is False
        assert backend._http_only is False
        assert backend._same_site == "strict"


# ---------------------------------------------------------------------------
# authenticate()
# ---------------------------------------------------------------------------


class TestAuthenticate:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_cookie(self) -> None:
        repo = _make_session_repo()
        backend = SessionCookieBackend(
            session_repository=repo,
            user_fetcher=AsyncMock(),
        )
        request = _make_request(session_id=None)

        result = await backend.authenticate(request)

        assert result is None
        repo.find_active.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_when_session_not_found(self) -> None:
        repo = _make_session_repo(find_active_result=None)
        backend = SessionCookieBackend(
            session_repository=repo,
            user_fetcher=AsyncMock(),
        )
        request = _make_request(session_id="stale-id")

        result = await backend.authenticate(request)

        assert result is None
        repo.find_active.assert_awaited_once_with("stale-id")

    @pytest.mark.asyncio
    async def test_returns_none_when_user_not_found(self) -> None:
        repo = _make_session_repo(
            find_active_result={"session_id": "sess-1", "user_id": "ghost-user"}
        )
        user_fetcher = AsyncMock(return_value=None)
        backend = SessionCookieBackend(
            session_repository=repo,
            user_fetcher=user_fetcher,
        )
        request = _make_request(session_id="sess-1")

        result = await backend.authenticate(request)

        assert result is None
        user_fetcher.assert_awaited_once_with("ghost-user")

    @pytest.mark.asyncio
    async def test_returns_user_on_valid_session(self) -> None:
        user = _make_user("user-42")
        repo = _make_session_repo(
            find_active_result={"session_id": "sess-ok", "user_id": "user-42"}
        )
        user_fetcher = AsyncMock(return_value=user)
        backend = SessionCookieBackend(
            session_repository=repo,
            user_fetcher=user_fetcher,
        )
        request = _make_request(session_id="sess-ok")

        result = await backend.authenticate(request)

        assert result is user
        user_fetcher.assert_awaited_once_with("user-42")

    @pytest.mark.asyncio
    async def test_updates_activity_on_valid_session(self) -> None:
        """Last-active timestamp must be refreshed for every valid authentication."""
        user = _make_user()
        repo = _make_session_repo(
            find_active_result={"session_id": "sess-ok", "user_id": "user-123"}
        )
        user_fetcher = AsyncMock(return_value=user)
        backend = SessionCookieBackend(
            session_repository=repo,
            user_fetcher=user_fetcher,
        )
        request = _make_request(session_id="sess-ok")

        await backend.authenticate(request)

        repo.update_activity.assert_awaited_once()
        args = repo.update_activity.call_args
        assert args[0][0] == "sess-ok"
        # Second arg is a datetime — must be UTC-aware
        ts: datetime = args[0][1]
        assert ts.tzinfo is not None

    @pytest.mark.asyncio
    async def test_does_not_update_activity_when_session_missing(self) -> None:
        repo = _make_session_repo(find_active_result=None)
        backend = SessionCookieBackend(
            session_repository=repo,
            user_fetcher=AsyncMock(),
        )
        request = _make_request(session_id="bad-id")

        await backend.authenticate(request)

        repo.update_activity.assert_not_called()

    @pytest.mark.asyncio
    async def test_uses_custom_cookie_name(self) -> None:
        user = _make_user()
        repo = _make_session_repo(
            find_active_result={"session_id": "s1", "user_id": "u1"}
        )
        backend = SessionCookieBackend(
            session_repository=repo,
            user_fetcher=AsyncMock(return_value=user),
            cookie_name="admin_session",
        )
        request = MagicMock()
        request.cookies = {"admin_session": "s1"}

        result = await backend.authenticate(request)

        assert result is user
        repo.find_active.assert_awaited_once_with("s1")


# ---------------------------------------------------------------------------
# login()
# ---------------------------------------------------------------------------


class TestLogin:
    @pytest.mark.asyncio
    async def test_returns_session_id_string(self) -> None:
        repo = _make_session_repo()
        backend = SessionCookieBackend(
            session_repository=repo,
            user_fetcher=AsyncMock(),
        )
        response = _make_response()

        session_id = await backend.login(response, user_id="user-1")

        assert isinstance(session_id, str)
        assert len(session_id) > 0

    @pytest.mark.asyncio
    async def test_inserts_session_record(self) -> None:
        repo = _make_session_repo()
        backend = SessionCookieBackend(
            session_repository=repo,
            user_fetcher=AsyncMock(),
        )
        response = _make_response()

        session_id = await backend.login(response, user_id="user-99", expires_in=3600)

        repo.insert.assert_awaited_once()
        payload: dict = repo.insert.call_args[0][0]
        assert payload["session_id"] == session_id
        assert payload["user_id"] == "user-99"
        assert payload["device_id"] == "ssr"
        assert "expires_at" in payload
        # expires_at must be a timezone-aware datetime
        expires_at: datetime = payload["expires_at"]
        assert expires_at.tzinfo is not None

    @pytest.mark.asyncio
    async def test_sets_cookie_on_response(self) -> None:
        repo = _make_session_repo()
        backend = SessionCookieBackend(
            session_repository=repo,
            user_fetcher=AsyncMock(),
            secure=True,
            http_only=True,
            same_site="lax",
        )
        response = _make_response()

        session_id = await backend.login(response, user_id="u1", expires_in=7200)

        response.set_cookie.assert_called_once_with(
            key="session_id",
            value=session_id,
            max_age=7200,
            secure=True,
            httponly=True,
            samesite="lax",
        )

    @pytest.mark.asyncio
    async def test_each_login_produces_unique_session_id(self) -> None:
        repo = _make_session_repo()
        backend = SessionCookieBackend(
            session_repository=repo,
            user_fetcher=AsyncMock(),
        )
        response = _make_response()

        id1 = await backend.login(response, user_id="u1")
        id2 = await backend.login(response, user_id="u1")

        assert id1 != id2


# ---------------------------------------------------------------------------
# logout()
# ---------------------------------------------------------------------------


class TestLogout:
    @pytest.mark.asyncio
    async def test_revokes_session_when_cookie_present(self) -> None:
        repo = _make_session_repo()
        backend = SessionCookieBackend(
            session_repository=repo,
            user_fetcher=AsyncMock(),
        )
        request = _make_request(session_id="sess-xyz")
        response = _make_response()

        await backend.logout(request, response)

        repo.revoke.assert_awaited_once_with("sess-xyz")

    @pytest.mark.asyncio
    async def test_clears_cookie_on_response(self) -> None:
        repo = _make_session_repo()
        backend = SessionCookieBackend(
            session_repository=repo,
            user_fetcher=AsyncMock(),
        )
        request = _make_request(session_id="sess-xyz")
        response = _make_response()

        await backend.logout(request, response)

        response.delete_cookie.assert_called_once_with(key="session_id")

    @pytest.mark.asyncio
    async def test_does_not_revoke_when_no_cookie(self) -> None:
        """logout must be safe to call even when the cookie is absent."""
        repo = _make_session_repo()
        backend = SessionCookieBackend(
            session_repository=repo,
            user_fetcher=AsyncMock(),
        )
        request = _make_request(session_id=None)
        response = _make_response()

        await backend.logout(request, response)

        repo.revoke.assert_not_called()
        # Cookie should still be cleared regardless
        response.delete_cookie.assert_called_once_with(key="session_id")

    @pytest.mark.asyncio
    async def test_uses_custom_cookie_name_for_logout(self) -> None:
        repo = _make_session_repo()
        backend = SessionCookieBackend(
            session_repository=repo,
            user_fetcher=AsyncMock(),
            cookie_name="admin_session",
        )
        request = MagicMock()
        request.cookies = {"admin_session": "s99"}
        response = _make_response()

        await backend.logout(request, response)

        repo.revoke.assert_awaited_once_with("s99")
        response.delete_cookie.assert_called_once_with(key="admin_session")
