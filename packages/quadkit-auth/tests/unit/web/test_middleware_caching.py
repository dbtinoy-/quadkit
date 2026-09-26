"""Tests for authentication middleware with caching"""

import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.auth.authn.core import User
from quadkit.auth.config import AuthMiddlewareConfig
from quadkit.auth.web import AuthMiddleware
from quadkit.contracts.auth.token import VerifiedToken
from quadkit.result import Ok


def _verified(user_id: str = "user123", *, name: str = "testuser", email: str = "test@example.com", roles: list[str] | None = None) -> VerifiedToken:
    """Helper to create a VerifiedToken for mocking."""
    return VerifiedToken(
        user_id=user_id,
        email=email,
        name=name,
        roles=roles or ["user"],
        permissions=[],
        expires_at=datetime(2099, 1, 1, tzinfo=UTC),
        key_id="default",
        token_type="access",
    )


@pytest.fixture
def auth_config():
    """Auth middleware config for testing."""
    return AuthMiddlewareConfig()


@pytest.fixture
def mock_auth_provider():
    """Mock auth provider for testing."""
    provider = AsyncMock()

    # Mock token verification — now returns Ok(VerifiedToken)
    provider.verify_token.return_value = Ok(_verified())

    # Mock user
    user = User(
        user_id="user123",
        name="testuser",
        email="test@example.com",
        roles=["user"],
    )
    provider.get_user.return_value = user

    return provider


@pytest.fixture
def auth_middleware(mock_auth_provider, auth_config):
    """Auth middleware instance."""
    return AuthMiddleware(mock_auth_provider, auth_config)


@pytest.fixture
def mock_request():
    """Mock request for testing."""
    request = MagicMock()
    request.headers = {"Authorization": "Bearer test_token"}
    request.url.path = "/api/test"
    request.state = MagicMock()
    request.scope = {}
    request.cookies = {}
    return request


class TestAuthMiddlewareCaching:
    """Test auth middleware token caching functionality."""

    @pytest.mark.asyncio
    async def test_token_cache_miss(
        self, auth_middleware, mock_auth_provider, mock_request,
    ):
        """Test token cache miss performs full authentication."""
        # Authenticate request
        user = await auth_middleware.authenticate_request(mock_request)

        # Verify user returned
        assert user is not None
        assert user.user_id == "user123"

        # Verify token verification and user lookup called
        mock_auth_provider.verify_token.assert_called_once_with("test_token")
        mock_auth_provider.get_user.assert_called_once_with("user123")

    @pytest.mark.asyncio
    async def test_token_cache_hit(
        self, auth_middleware, mock_auth_provider, mock_request,
    ):
        """Test token cache hit skips JWT decode and DB lookup."""
        # First call - cache miss
        user1 = await auth_middleware.authenticate_request(mock_request)

        # Reset mocks
        mock_auth_provider.verify_token.reset_mock()
        mock_auth_provider.get_user.reset_mock()

        # Second call - should hit cache
        user2 = await auth_middleware.authenticate_request(mock_request)

        # Verify same user returned
        assert user1 is user2

        # Verify JWT decode and DB lookup were NOT called on second request
        mock_auth_provider.verify_token.assert_not_called()
        mock_auth_provider.get_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_token_cache_expiration(
        self, auth_middleware, mock_auth_provider, mock_request,
    ):
        """Test token cache expires after TTL."""
        # Set very short TTL for testing
        auth_middleware.token_cache._ttl = 0.1

        # First call - cache miss
        user1 = await auth_middleware.authenticate_request(mock_request)

        # Wait for cache to expire
        time.sleep(0.2)

        # Reset mocks
        mock_auth_provider.verify_token.reset_mock()
        mock_auth_provider.get_user.reset_mock()

        # Second call - should miss cache and re-verify
        user2 = await auth_middleware.authenticate_request(mock_request)

        # Verify same user returned
        assert user1.user_id == user2.user_id

        # Verify JWT decode and DB lookup were called again
        mock_auth_provider.verify_token.assert_called_once()
        mock_auth_provider.get_user.assert_called_once()

    @pytest.mark.asyncio
    async def test_different_tokens_cached_separately(
        self, auth_middleware, mock_auth_provider,
    ):
        """Test different tokens are cached separately."""
        # Mock different users for different tokens
        user1 = User(
            user_id="user1", name="user1", email="user1@example.com", roles=["user"],
        )
        user2 = User(
            user_id="user2", name="user2", email="user2@example.com", roles=["user"],
        )

        # Configure mock to return different users based on token
        mock_auth_provider.verify_token.side_effect = None
        mock_auth_provider.verify_token.return_value = Ok(_verified("user1", name="user1", email="user1@example.com"))

        def mock_verify_token(token):
            if token == "token1":
                return Ok(_verified("user1", name="user1", email="user1@example.com"))
            elif token == "token2":
                return Ok(_verified("user2", name="user2", email="user2@example.com"))
            return Ok(_verified())

        def mock_get_user(user_id):
            if user_id == "user1":
                return user1
            elif user_id == "user2":
                return user2
            return None

        mock_auth_provider.verify_token.side_effect = mock_verify_token
        mock_auth_provider.get_user.side_effect = mock_get_user

        # Create requests with different tokens
        request1 = MagicMock()
        request1.headers = {"Authorization": "Bearer token1"}
        request1.state = MagicMock()
        request1.cookies = {}
        request1.client.host = "127.0.0.1"

        request2 = MagicMock()
        request2.headers = {"Authorization": "Bearer token2"}
        request2.state = MagicMock()
        request2.cookies = {}
        request2.client.host = "127.0.0.1"

        # Authenticate both requests
        result1 = await auth_middleware.authenticate_request(request1)
        result2 = await auth_middleware.authenticate_request(request2)

        # Verify different users returned
        assert result1.user_id == "user1"
        assert result2.user_id == "user2"

        # Verify both tokens were verified and users looked up
        assert mock_auth_provider.verify_token.call_count == 2
        assert mock_auth_provider.get_user.call_count == 2
