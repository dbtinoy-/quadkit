"""Tests for JWT key rotation grace period functionality.

Covers audit item A1 — configurable ``key_rotation_grace_period_seconds``
prevents immediate user logout when a signing key is rotated.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import jwt
import pytest
from pydantic import SecretStr

from quadkit.auth import constants as const
from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.config import AuthConfig, JWTConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_token_manager(grace_period_seconds: int = 3600) -> JWTTokenManager:
    mock_cache = AsyncMock()
    mock_cache.exists = AsyncMock(return_value=False)
    return JWTTokenManager(
        current_key_id="key-new",
        keys={
            "key-new": SecretStr("new-secret-key-at-least-32-chars-xxxx"),
            "key-old": SecretStr("old-secret-key-at-least-32-chars-xxxx"),
        },
        access_expiration_hours=1,
        cache_service=mock_cache,
        grace_period_seconds=grace_period_seconds,
    )


def _sign_with_key(manager: JWTTokenManager, kid: str) -> str:
    """Return a valid access token signed with *kid*."""
    key = manager.keys[kid]
    assert hasattr(key, "get_secret_value"), "expected SecretStr"
    payload = {
        "sub": "user-123",
        "type": "access",
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(
        payload,
        key.get_secret_value(),
        algorithm="HS256",
        headers={"kid": kid},
    )


# ---------------------------------------------------------------------------
# Tests — grace_period_seconds parameter
# ---------------------------------------------------------------------------


class TestGracePeriodDefault:
    """Verify the default grace period matches the constant."""

    def test_default_grace_period_matches_constant(self) -> None:
        """JWTTokenManager defaults grace_period_seconds to the module constant."""
        manager = JWTTokenManager(current_key_id="key", keys={"key": SecretStr("a" * 32)})
        assert manager.grace_period_seconds == const.DEFAULT_JWT_KEY_ROTATION_GRACE_PERIOD_SECONDS

    def test_default_constant_is_one_hour(self) -> None:
        """The default constant value is 3600 (1 hour)."""
        assert const.DEFAULT_JWT_KEY_ROTATION_GRACE_PERIOD_SECONDS == 3600

    def test_custom_grace_period_stored(self) -> None:
        """A custom grace_period_seconds is stored on the instance."""
        manager = JWTTokenManager(
            current_key_id="key",
            keys={"key": SecretStr("a" * 32)},
            grace_period_seconds=7200,
        )
        assert manager.grace_period_seconds == 7200


class TestJWTConfigGracePeriodField:
    """Verify JWTConfig exposes key_rotation_grace_period."""

    def test_jwt_config_has_grace_period_field(self) -> None:
        """JWTConfig includes key_rotation_grace_period with default 3600."""
        cfg = JWTConfig(secret_key="some-long-secret-key-for-testing-minimum-length")
        assert hasattr(cfg, "key_rotation_grace_period")
        assert cfg.key_rotation_grace_period.total_seconds == 3600

    def test_jwt_config_custom_grace_period(self) -> None:
        """JWTConfig accepts a custom key_rotation_grace_period."""
        from quadkit.contracts.core import Duration

        cfg = JWTConfig(
            secret_key="some-long-secret-key-for-testing-minimum-length",
            key_rotation_grace_period=Duration.seconds(7200),
        )
        assert cfg.key_rotation_grace_period.total_seconds == 7200


# ---------------------------------------------------------------------------
# Tests — cleanup respects grace period
# ---------------------------------------------------------------------------


class TestCleanupOldKeys:
    """Verify _cleanup_old_keys uses self.grace_period_seconds."""

    @pytest.mark.asyncio
    async def test_key_within_grace_period_is_retained(self) -> None:
        """Keys created within the grace period are NOT cleaned up on rotate."""
        manager = _make_token_manager(grace_period_seconds=3600)

        # Rotate away from key-old — it was just added so age ≈ 0 s
        await manager.rotate_key("key-new2", "new-secret-key-v2-at-least-32-chars")

        # key-old should still exist (age < 3600 s)
        assert "key-old" in manager.keys

    @pytest.mark.asyncio
    async def test_key_past_grace_period_is_removed(self) -> None:
        """Keys older than grace_period_seconds are removed on the next rotate."""
        manager = _make_token_manager(grace_period_seconds=0)  # expire immediately

        # Backdate key-old's metadata so it appears expired
        manager._key_meta["key-old"]["created_at"] = datetime(2000, 1, 1, tzinfo=UTC)

        # Rotate — cleanup runs afterwards
        await manager.rotate_key("key-new2", "new-secret-key-v2-at-least-32-chars")

        # key-old age >> 0 s, so it should be gone
        assert "key-old" not in manager.keys

    @pytest.mark.asyncio
    async def test_current_key_never_removed(self) -> None:
        """The current signing key is never cleaned up, even with grace_period_seconds=0."""
        manager = _make_token_manager(grace_period_seconds=0)

        # Backdate the current key's metadata
        manager._key_meta["key-new"]["created_at"] = datetime(2000, 1, 1, tzinfo=UTC)

        # Rotate so we still have a current key reference
        await manager.rotate_key("key-latest", "latest-secret-key-at-least-32-chars")

        # key-latest is now current — must NOT be removed
        assert "key-latest" in manager.keys


# ---------------------------------------------------------------------------
# Tests — token verifiability during grace window
# ---------------------------------------------------------------------------


class TestTokenVerifiabilityDuringGracePeriod:
    """Old-key tokens remain verifiable while the key is within grace period."""

    @pytest.mark.asyncio
    async def test_token_signed_with_old_key_verifies_during_grace(self) -> None:
        """A token signed before key rotation is still valid inside the grace window."""
        manager = _make_token_manager(grace_period_seconds=3600)

        # Sign with key-old *before* rotation
        old_token = _sign_with_key(manager, "key-old")

        # Rotate to a new key
        await manager.rotate_key("key-new2", "new-secret-key-v2-at-least-32-chars")

        # key-old is within grace period → token should still verify
        result = await manager.verify_token(old_token, "access")
        assert result.is_ok(), f"Expected Ok, got: {result.unwrap_err()}"

    @pytest.mark.asyncio
    async def test_token_signed_with_expired_key_fails_after_grace(self) -> None:
        """A token signed by a key past the grace window is rejected."""
        manager = _make_token_manager(grace_period_seconds=0)

        # Sign with key-old
        old_token = _sign_with_key(manager, "key-old")

        # Backdate key-old so cleanup removes it on rotate
        manager._key_meta["key-old"]["created_at"] = datetime(2000, 1, 1, tzinfo=UTC)

        # Rotate — this triggers _cleanup_old_keys which removes key-old
        await manager.rotate_key("key-new2", "new-secret-key-v2-at-least-32-chars")

        # key-old is gone → token should fail
        from quadkit.auth.exceptions import TokenInvalidError

        result = await manager.verify_token(old_token, "access")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), TokenInvalidError)

    @pytest.mark.asyncio
    async def test_new_token_after_rotation_uses_new_key(self) -> None:
        """Tokens issued after rotation use the new key."""
        manager = _make_token_manager(grace_period_seconds=3600)
        await manager.rotate_key("key-new2", "new-secret-key-v2-at-least-32-chars")

        # Issue a new token
        from quadkit.auth.authn.core import User

        user = User(
            user_id="user-1",
            name="Alice",
            email="alice@example.com",
            roles=[],
            permissions=[],
        )
        new_token = manager.create_access_token(user)
        header = jwt.get_unverified_header(new_token)
        assert header.get("kid") == "key-new2"
