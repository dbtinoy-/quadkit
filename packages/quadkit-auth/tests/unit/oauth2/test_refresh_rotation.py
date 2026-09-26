"""Unit tests for refresh token rotation (FAANG finding 06.C-02).

On each successful refresh exchange the **old** refresh token must be
atomically revoked and a **new** one issued.  These tests verify that:

- The used refresh token is blacklisted immediately after exchange.
- A distinct refresh token is returned in the new token pair.
- Replaying the used token is rejected (replay-attack protection).
- Replay detection escalates to full-session revocation.
- Rotation works via the in-process fallback when no cache is wired.
"""

from __future__ import annotations

import hashlib

import pytest
from pydantic import SecretStr

from quadkit.auth.authn.core import User
from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.exceptions import BlacklistedTokenError, TokenError

# ── Test doubles ─────────────────────────────────────────────────────────────

_SECRET = "test-secret-key-at-least-32-bytes!!"
_KEY_ID = "k1"


class _MockCache:
    """Minimal in-process cache stub that supports the blacklist operations."""

    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    async def get(self, key: str) -> object | None:
        return self._store.get(key)

    async def set(self, key: str, value: object, ttl: int | None = None) -> bool:
        self._store[key] = value
        return True

    async def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

    async def exists(self, key: str) -> bool:
        return key in self._store


# ── Helpers ───────────────────────────────────────────────────────────────────


def _build_manager(cache: _MockCache | None = None) -> JWTTokenManager:
    """Return a ``JWTTokenManager`` wired to *cache* (or no cache)."""
    return JWTTokenManager(
        current_key_id=_KEY_ID,
        keys={_KEY_ID: SecretStr(_SECRET)},
        access_expiration_hours=1,
        refresh_expiration_days=30,
        cache_service=cache,
    )


def _make_user() -> User:
    return User(
        user_id="user-42",
        name="Alice",
        email="alice@example.com",
        roles=["user"],
        permissions=["read"],
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestRefreshTokenRotation:
    """Refresh tokens MUST be rotated on each successful exchange (06.C-02)."""

    @pytest.mark.asyncio
    async def test_old_refresh_token_revoked_on_exchange(self) -> None:
        """After a successful refresh, the used token must be blacklisted."""
        cache = _MockCache()
        manager = _build_manager(cache)
        user = _make_user()

        token_pair = manager.create_token_pair(user)
        old_refresh = token_pair.refresh_token

        # Act: exchange the refresh token for a new pair
        new_pair = await manager.refresh_access_token(old_refresh)

        assert new_pair is not None

        # The old refresh token hash must now be present in the blacklist
        old_hash = hashlib.sha256(old_refresh.encode()).hexdigest()
        blacklist_key = f"jwt:blacklist:{old_hash}"
        assert await cache.exists(blacklist_key), (
            "Old refresh token must be blacklisted immediately after rotation"
        )

    @pytest.mark.asyncio
    async def test_new_refresh_token_issued_on_exchange(self) -> None:
        """After a successful refresh, a NEW (distinct) refresh token must be issued."""
        cache = _MockCache()
        manager = _build_manager(cache)
        user = _make_user()

        token_pair = manager.create_token_pair(user)
        old_refresh = token_pair.refresh_token

        new_pair = await manager.refresh_access_token(old_refresh)

        assert new_pair.refresh_token != old_refresh, (
            "Rotated refresh token must differ from the consumed token"
        )
        assert new_pair.token != token_pair.token, (
            "New access token must also differ from the old one"
        )

    @pytest.mark.asyncio
    async def test_revoked_token_cannot_be_reused(self) -> None:
        """Once used (and therefore blacklisted), a refresh token must be rejected."""
        cache = _MockCache()
        manager = _build_manager(cache)
        user = _make_user()

        token_pair = manager.create_token_pair(user)
        old_refresh = token_pair.refresh_token

        # First exchange: legitimate use
        await manager.refresh_access_token(old_refresh)

        # Second exchange: replay — must fail
        with pytest.raises((BlacklistedTokenError, TokenError)):
            await manager.refresh_access_token(old_refresh)

    @pytest.mark.asyncio
    async def test_replay_triggers_full_session_revocation(self) -> None:
        """Presenting a blacklisted refresh token must revoke ALL user sessions."""
        cache = _MockCache()
        manager = _build_manager(cache)
        user = _make_user()

        token_pair = manager.create_token_pair(user)
        old_refresh = token_pair.refresh_token

        # Legitimate first use
        await manager.refresh_access_token(old_refresh)

        # Replay attack
        with pytest.raises(BlacklistedTokenError):
            await manager.refresh_access_token(old_refresh)

        # The user-level revocation sentinel must have been written
        user_blacklist_key = f"jwt:blacklist:user:{user.user_id}"
        assert await cache.exists(user_blacklist_key), (
            "Full session revocation sentinel must exist after replay detection"
        )

    @pytest.mark.asyncio
    async def test_rotation_without_cache_uses_in_process_fallback(self) -> None:
        """Rotation must work via the in-process fallback when no cache is configured."""
        manager = _build_manager(cache=None)
        user = _make_user()

        token_pair = manager.create_token_pair(user)
        old_refresh = token_pair.refresh_token

        # First exchange: succeeds
        new_pair = await manager.refresh_access_token(old_refresh)
        assert new_pair.refresh_token != old_refresh

        # Replay: must be rejected even without Redis
        with pytest.raises((BlacklistedTokenError, TokenError)):
            await manager.refresh_access_token(old_refresh)
