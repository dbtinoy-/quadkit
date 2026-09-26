"""Tests for OAuth2 refresh token rotation (06.C-02).

Verifies that :meth:`~quadkit.auth.authn.jwt.JWTTokenManager.refresh_with_rotation`:

- Returns ``Ok(TokenPair)`` with fresh access and refresh token strings.
- Blacklists the consumed refresh token so it cannot be reused.
- Returns ``Err`` when given an access token instead of a refresh token.
- Returns ``Err`` when given a completely invalid token string.
- Returns ``Err`` on a reuse-attempt of an already-rotated refresh token.
"""

from __future__ import annotations

import pytest

from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.models.user import User
from quadkit.auth.types import TokenPair
from quadkit.validation import SecretStr

_SECRET = "test-secret-that-is-at-least-32-chars-long"


def _make_manager() -> JWTTokenManager:
    """Return a test-ready JWTTokenManager with a single symmetric key."""
    return JWTTokenManager(
        current_key_id="default",
        keys={"default": SecretStr(_SECRET)},
        access_expiration_hours=1,
        refresh_expiration_days=7,
    )


def _make_user() -> User:
    """Return a minimal User fixture."""
    return User(
        user_id="user-1",
        name="Alice",
        email="alice@example.com",
        roles=["user"],
        permissions=[],
    )


class TestRefreshTokenRotation:
    """Suite covering refresh_with_rotation on JWTTokenManager."""

    @pytest.mark.asyncio
    async def test_rotation_returns_ok_token_pair(self) -> None:
        """Successful rotation returns ``Ok(TokenPair)`` with non-empty strings."""
        manager = _make_manager()
        user = _make_user()
        auth_token = manager.create_token_pair(user)
        assert auth_token.refresh_token is not None

        result = await manager.refresh_with_rotation(auth_token.refresh_token)

        assert result.is_ok()
        pair = result.unwrap()
        assert isinstance(pair, TokenPair)
        assert pair.access != ""
        assert pair.refresh != ""

    @pytest.mark.asyncio
    async def test_rotation_issues_different_tokens(self) -> None:
        """Rotated tokens must differ from the original tokens."""
        manager = _make_manager()
        user = _make_user()
        auth_token = manager.create_token_pair(user)
        original_access = auth_token.token
        original_refresh = auth_token.refresh_token
        assert original_refresh is not None

        result = await manager.refresh_with_rotation(original_refresh)

        assert result.is_ok()
        pair = result.unwrap()
        assert pair.access != original_access
        assert pair.refresh != original_refresh

    @pytest.mark.asyncio
    async def test_rotation_invalidates_old_refresh_token(self) -> None:
        """After rotation, the consumed refresh token must be rejected."""
        manager = _make_manager()
        user = _make_user()
        auth_token = manager.create_token_pair(user)
        original_refresh = auth_token.refresh_token
        assert original_refresh is not None

        # First rotation succeeds
        first = await manager.refresh_with_rotation(original_refresh)
        assert first.is_ok()

        # Reusing the same token must now fail
        second = await manager.refresh_with_rotation(original_refresh)
        assert second.is_err()

    @pytest.mark.asyncio
    async def test_rotation_new_refresh_token_is_valid(self) -> None:
        """The refresh token returned by rotation must itself be rotateable."""
        manager = _make_manager()
        user = _make_user()
        auth_token = manager.create_token_pair(user)
        original_refresh = auth_token.refresh_token
        assert original_refresh is not None

        first = await manager.refresh_with_rotation(original_refresh)
        assert first.is_ok()
        pair = first.unwrap()

        # The new refresh token from the first rotation must also work
        second = await manager.refresh_with_rotation(pair.refresh)
        assert second.is_ok()

    @pytest.mark.asyncio
    async def test_rotation_fails_for_access_token(self) -> None:
        """Passing an access token (wrong type) must return ``Err``."""
        manager = _make_manager()
        user = _make_user()
        auth_token = manager.create_token_pair(user)

        result = await manager.refresh_with_rotation(auth_token.token)

        assert result.is_err()

    @pytest.mark.asyncio
    async def test_rotation_fails_for_invalid_token_string(self) -> None:
        """A completely invalid token string must return ``Err``."""
        manager = _make_manager()

        result = await manager.refresh_with_rotation("not.a.valid.jwt.token")

        assert result.is_err()

    @pytest.mark.asyncio
    async def test_rotation_result_is_ok_type(self) -> None:
        """Result type check: successful rotation unwraps to TokenPair."""
        manager = _make_manager()
        user = _make_user()
        auth_token = manager.create_token_pair(user)
        assert auth_token.refresh_token is not None

        result = await manager.refresh_with_rotation(auth_token.refresh_token)

        assert result.is_ok()
        pair = result.unwrap()
        assert isinstance(pair.access, str)
        assert isinstance(pair.refresh, str)
