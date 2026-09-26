"""Tests for JWT token management with key rotation"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import jwt
import pytest

from quadkit.auth.authn.core import User
from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.validation import SecretStr


class TestJWTTokenManager:
    """Test JWT token manager with key rotation support."""

    @pytest.fixture
    def user(self) -> User:
        """Create test user."""
        return User(
            user_id="user-123",
            name="testuser",
            email="test@example.com",
            roles=["user"],
            permissions=["read"],
        )

    @pytest.fixture
    def token_manager(self) -> JWTTokenManager:
        """Create JWT token manager with multiple keys."""
        mock_cache = AsyncMock()
        mock_cache.exists.return_value = False
        return JWTTokenManager(
            current_key_id="key-2024-01",
            keys={
                "key-2024-01": SecretStr("current-secret-key-at-least-32-chars"),
                "key-2023-10": SecretStr("old-secret-key-at-least-32-chars-long"),
            },
            access_expiration_hours=1,
            refresh_expiration_days=30,
            cache_service=mock_cache,
        )

    def test_create_access_token_includes_key_id(self, token_manager, user):
        """Test that access tokens include key ID in header."""
        token = token_manager.create_access_token(user)

        # Decode header to check key ID
        header = jwt.get_unverified_header(token)
        assert header.get("kid") == "key-2024-01"

        # Verify token with correct key
        payload = jwt.decode(
            token, token_manager.keys["key-2024-01"].get_secret_value(), algorithms=["HS256"],
        )
        assert payload["sub"] == user.user_id
        assert payload["type"] == "access"

    def test_create_refresh_token_includes_key_id(self, token_manager, user):
        """Test that refresh tokens include key ID in header."""
        token = token_manager.create_refresh_token(user)

        # Decode header to check key ID
        header = jwt.get_unverified_header(token)
        assert header.get("kid") == "key-2024-01"

        # Verify token with correct key
        payload = jwt.decode(
            token, token_manager.keys["key-2024-01"].get_secret_value(), algorithms=["HS256"],
        )
        assert payload["sub"] == user.user_id
        assert payload["type"] == "refresh"

    @pytest.mark.asyncio
    async def test_verify_token_with_current_key(self, token_manager, user):
        """Test token verification with current key."""
        token = token_manager.create_access_token(user)

        result = await token_manager.verify_token(token, "access")
        assert result.is_ok()
        verified = result.unwrap()
        assert verified.user_id == user.user_id
        assert verified.token_type == "access"

    @pytest.mark.asyncio
    async def test_verify_token_with_old_key(self, token_manager, user):
        """Test token verification with old key (graceful rotation)."""
        # Create token with old key
        old_token = jwt.encode(
            {
                "sub": user.user_id,
                "type": "access",
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int(
                    (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp(),
                ),
            },
            token_manager.keys["key-2023-10"].get_secret_value(),
            algorithm="HS256",
            headers={"kid": "key-2023-10"},
        )

        # Should still verify with old key
        result = await token_manager.verify_token(old_token, "access")
        assert result.is_ok()
        assert result.unwrap().user_id == user.user_id

    @pytest.mark.asyncio
    async def test_verify_token_with_unknown_key(self, token_manager, user):
        """Test token verification fails with unknown key."""
        # Create token with unknown key
        import jwt

        unknown_token = jwt.encode(
            {
                "sub": user.user_id,
                "type": "access",
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int(
                    (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp(),
                ),
            },
            "unknown-secret-key-at-least-32-bytes-long",
            algorithm="HS256",
            headers={"kid": "unknown-key"},
        )

        # Should fail verification
        from quadkit.auth.exceptions import TokenInvalidError
        result = await token_manager.verify_token(unknown_token, "access")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), TokenInvalidError)

    @pytest.mark.asyncio
    async def test_rotate_key(self, token_manager, user):
        """Test key rotation."""
        # Create token with current key
        old_token = token_manager.create_access_token(user)

        # Rotate to new key (must be at least 32 bytes for HS256)
        await token_manager.rotate_key("key-2024-04", "new-secret-key-at-least-32-bytes-long")

        # Verify current key ID changed
        assert token_manager.current_key_id == "key-2024-04"

        # Verify new key is in keys dict and is at least 32 bytes
        assert "key-2024-04" in token_manager.keys
        new_key = token_manager.keys["key-2024-04"]
        assert isinstance(new_key, SecretStr)
        assert len(new_key.get_secret_value()) >= 32

        # Old token should still verify (graceful rotation)
        result = await token_manager.verify_token(old_token, "access")
        assert result.is_ok()

        # New tokens should use new key
        new_token = token_manager.create_access_token(user)
        header = jwt.get_unverified_header(new_token)
        assert header.get("kid") == "key-2024-04"

    @pytest.mark.asyncio
    async def test_create_token_pair_includes_key_ids(self, token_manager, user):
        """Test that token pair includes key IDs."""

        token_pair = token_manager.create_token_pair(user)

        # Check access token
        access_header = jwt.get_unverified_header(token_pair.token)
        assert access_header.get("kid") == "key-2024-01"

        # Check refresh token
        refresh_header = jwt.get_unverified_header(token_pair.refresh_token)
        assert refresh_header.get("kid") == "key-2024-01"

    @pytest.mark.asyncio
    async def test_refresh_access_token_uses_current_key(self, token_manager, user):
        """Test that refreshed access tokens use current key."""

        # Create refresh token
        refresh_token = token_manager.create_refresh_token(user)

        # Refresh access token
        new_token_pair = await token_manager.refresh_access_token(refresh_token)
        assert new_token_pair is not None

        # Check that new access token uses current key
        header = jwt.get_unverified_header(new_token_pair.token)
        assert header.get("kid") == "key-2024-01"

    @pytest.mark.asyncio
    async def test_blacklist_still_works_with_key_rotation(self, token_manager, user):
        """Test that token blacklisting works with key rotation."""
        # Mock cache service - never blacklisted
        cache_service = AsyncMock()
        cache_service.exists = AsyncMock(return_value=False)
        token_manager.cache_service = cache_service

        # Rotate key
        await token_manager.rotate_key("key-2024-04", "new-secret-key-at-least-32-bytes")

        # Create new token with new key
        new_token = token_manager.create_access_token(user)

        # New token should work (not blacklisted)
        new_result = await token_manager.verify_token(new_token, "access")
        assert new_result.is_ok()
