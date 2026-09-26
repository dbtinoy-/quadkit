"""JWTTokenManager token lifecycle tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr

from quadkit.auth.models import AuthToken
import quadkit.auth as la
from quadkit.auth.authn.core import User
from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.authn.schemas import RegisterRequest
from quadkit.auth.authn.security import PasswordHasher, PasswordPolicy
from quadkit.auth.di import AuthenticationProvider, AuthorizationProvider
from quadkit.auth.storage.db_stores import (
    MongoDBUserStore,
    RedisUserStore,
    SQLUserStore,
)
from quadkit.auth.storage.token_store import InMemoryUserStore
from quadkit.auth.exceptions import (
    TokenExpiredError,
    InvalidTokenError,
    BlacklistedTokenError,
)
from quadkit.auth.exceptions import (
    TokenAudienceError,
    TokenBlacklistedError,
    TokenExpiredError as TokenExpiredErrorAuth,
    TokenInvalidError,
)
from quadkit.contracts.auth.token import VerifiedToken
from quadkit.result import Err, Ok


class TestJWTTokenManager:
    """Test JWT token management"""

    def setup_method(self):
        """Setup test method"""
        self.secret = SecretStr("test_secret_key_12345678901234567890123456789123")
        self.mock_cache = AsyncMock()
        self.mock_cache.exists.return_value = False
        self.manager = JWTTokenManager(
            current_key_id="default",
            keys={"default": self.secret},
            cache_service=self.mock_cache,
            access_expiration_hours=1,
            refresh_expiration_days=30,
        )

    def test_create_access_token(self):
        """Test access token creation"""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["user"],
            permissions=["read"],
        )

        token = self.manager.create_access_token(user)
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_token_pair(self):
        """Test token pair creation"""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["user"],
        )

        token_pair = self.manager.create_token_pair(user)
        assert isinstance(token_pair, AuthToken)
        assert token_pair.token is not None
        assert token_pair.refresh_token is not None
        assert token_pair.expires_at is not None
        assert token_pair.refresh_expires_at is not None

    @pytest.mark.asyncio
    async def test_verify_token(self):
        """Test token verification"""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["user"],
        )

        token = self.manager.create_access_token(user)
        result = await self.manager.verify_token(token)

        assert result.is_ok()
        verified = result.unwrap()
        assert verified.user_id == user.user_id
        assert verified.name == user.name
        assert "username" not in verified.__dataclass_fields__
        assert verified.roles == user.roles

    @pytest.mark.asyncio
    async def test_verify_expired_token(self):
        """Test expired token verification"""
        # Create token that expires immediately
        manager = JWTTokenManager(
            current_key_id="default",
            keys={"default": self.secret},
            cache_service=self.mock_cache,
            access_expiration_hours=-1,  # Already expired
        )

        user = User(user_id="user123", name="testuser", email="test@example.com")
        token = manager.create_access_token(user)

        result = await manager.verify_token(token)
        assert result.is_err()
        assert isinstance(result.unwrap_err(), TokenExpiredErrorAuth)

    @pytest.mark.asyncio
    async def test_verify_invalid_token(self):
        """Test invalid token verification"""
        result = await self.manager.verify_token("invalid.token.here")
        assert result.is_err()
        assert isinstance(result.unwrap_err(), TokenInvalidError)

    @pytest.mark.asyncio
    async def test_refresh_token(self):
        """Test token refresh"""
        user = User(user_id="user123", name="testuser", email="test@example.com")

        # Mock verify token for refresh: return Ok(VerifiedToken) for refresh tokens
        def _refresh_verified() -> VerifiedToken:
            return VerifiedToken(
                user_id="user123",
                email="test@example.com",
                name="testuser",
                roles=[],
                permissions=[],
                expires_at=datetime(2099, 1, 1, tzinfo=UTC),
                key_id="default",
                token_type="refresh",
            )

        original_verify = self.manager.verify_token
        async def mock_verify(token, token_type="access", **kwargs):
            if token_type == "refresh":
                return Ok(_refresh_verified())
            return await original_verify(token, token_type, **kwargs)
        self.manager.verify_token = mock_verify

        # Mock logout for refresh
        self.manager.logout = AsyncMock(return_value=True)

        token_pair = self.manager.create_token_pair(user)
        new_token = await self.manager.refresh_access_token(token_pair.refresh_token)

        assert new_token is not None
        assert new_token.token is not None
        assert new_token.refresh_token is not None

        # Verify the old token was revoked
        self.manager.logout.assert_called_once_with(token_pair.refresh_token)

    @pytest.mark.asyncio
    async def test_refresh_token_reuse_detection(self):
        """Test that reusing a blacklisted refresh token revokes all user tokens."""
        user = User(user_id="user123", name="testuser", email="test@example.com")
        token_pair = self.manager.create_token_pair(user)

        # Mock verify_token to return Err(TokenBlacklistedError) — new Result-based API
        self.manager.verify_token = AsyncMock(
            return_value=Err(TokenBlacklistedError("Revoked"))
        )
        self.manager.logout_all_user_tokens = AsyncMock()

        with pytest.raises(BlacklistedTokenError, match="Refresh token reuse detected. All sessions revoked."):
            await self.manager.refresh_access_token(token_pair.refresh_token)

        # Ensure all user tokens were logged out
        self.manager.logout_all_user_tokens.assert_called_once_with("user123")

    @pytest.mark.asyncio
    async def test_verify_token_with_audience(self):
        """Test token audience validation."""
        user = User(user_id="user123", name="testuser", email="test@example.com")

        # Create token with audience claim
        token = self.manager.create_access_token(user, additional_claims={"aud": "my-api"})

        # Verify with correct audience
        result = await self.manager.verify_token(token, expected_audience="my-api")
        assert result.is_ok()
        assert result.unwrap().audience == "my-api"

        # Verify with incorrect audience
        result2 = await self.manager.verify_token(token, expected_audience="wrong-api")
        assert result2.is_err()
        assert isinstance(result2.unwrap_err(), TokenAudienceError)


