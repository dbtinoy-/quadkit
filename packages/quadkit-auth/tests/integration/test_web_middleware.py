"""Tests for web middleware components"""

from pydantic import SecretStr
import pytest

from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.authn.security import PasswordHasher
from quadkit.auth.di.sub_providers.authentication_provider import (
    AuthenticationProvider,
)
from quadkit.auth.web import AuthMiddleware, AuthMiddlewareConfig


class MockCache:
    """Simple mock cache for testing"""

    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def set(self, key, value, ttl=None):
        self.data[key] = value
        return True

    async def delete(self, key):
        return self.data.pop(key, None) is not None

    async def exists(self, key):
        return key in self.data


class TestAuthMiddleware:
    """Test authentication middleware"""

    def setup_method(self):
        """Setup test method"""
        self.cache = MockCache()
        self.jwt_manager = JWTTokenManager(
            SecretStr("test_secret_key_at_least_32_bytes_long"),
            cache_service=self.cache,
        )
        self.provider = AuthenticationProvider(
            token_manager=self.jwt_manager,
        )
        # Make auth optional for testing
        config = AuthMiddlewareConfig(optional_auth=True)
        self.middleware = AuthMiddleware(self.provider, config)

    @pytest.mark.asyncio
    async def test_middleware_sets_user_in_state_and_scope(self):
        """Test that middleware sets user in both request.state and request.scope"""
        # Create a test user directly in the store (providers don't own user creation)
        hashed_pw = await PasswordHasher().hash("Password123!")
        user = await self.provider.user_store.create_user(
            name="testuser",
            email="test@example.com",
            hashed_password=hashed_pw,
        )

        # Create a mock request with authorization header
        token_pair = self.provider.service.create_token(user)

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "query_string": b"",
            "headers": [
                (b"authorization", f"Bearer {token_pair.token}".encode()),
            ],
            "state": {},
        }

        async def mock_receive():
            return {"type": "http.request"}

        # Mock ASGI app (call_next equivalent)
        async def mock_app(s, r, sn):
            await sn(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [],
                }
            )
            await sn(
                {
                    "type": "http.response.body",
                    "body": b"ok",
                }
            )

        self.middleware.set_app(mock_app)

        # Capture sent messages
        sent_messages = []

        async def mock_send(message):
            sent_messages.append(message)

        # Process the request through middleware
        await self.middleware(scope, mock_receive, mock_send)

        # Verify user is set in both places
        assert scope["user"] == user
        assert scope["state"]["user"] == user
        assert scope["state"]["user_id"] == str(user.user_id)

        # Verify response was sent
        assert any(
            msg["type"] == "http.response.start" and msg["status"] == 200
            for msg in sent_messages
        )

    @pytest.mark.asyncio
    async def test_middleware_no_auth_header(self):
        """Test middleware with no authorization header"""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "query_string": b"",
            "headers": [],
            "state": {},
        }

        async def mock_receive():
            return {"type": "http.request"}

        async def mock_app(s, r, sn):
            await sn({"type": "http.response.start", "status": 200, "headers": []})
            await sn({"type": "http.response.body", "body": b"ok"})

        self.middleware.set_app(mock_app)
        sent_messages = []

        async def mock_send(message):
            sent_messages.append(message)

        await self.middleware(scope, mock_receive, mock_send)

        # User should be None
        assert scope["state"]["user"] is None

    @pytest.mark.asyncio
    async def test_middleware_invalid_token(self):
        """Test middleware with invalid token"""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "query_string": b"",
            "headers": [
                (b"authorization", b"Bearer invalid.token.here"),
            ],
            "state": {},
        }

        async def mock_receive():
            return {"type": "http.request"}

        async def mock_app(s, r, sn):
            await sn({"type": "http.response.start", "status": 200, "headers": []})
            await sn({"type": "http.response.body", "body": b"ok"})

        self.middleware.set_app(mock_app)
        sent_messages = []

        async def mock_send(message):
            sent_messages.append(message)

        await self.middleware(scope, mock_receive, mock_send)

        # User should be None
        assert scope["state"]["user"] is None

    @pytest.mark.asyncio
    async def test_middleware_malformed_auth_header(self):
        """Test middleware with malformed authorization header"""
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "query_string": b"",
            "headers": [
                (b"authorization", b"InvalidFormat"),
            ],
            "state": {},
        }

        async def mock_receive():
            return {"type": "http.request"}

        async def mock_app(s, r, sn):
            await sn({"type": "http.response.start", "status": 200, "headers": []})
            await sn({"type": "http.response.body", "body": b"ok"})

        self.middleware.set_app(mock_app)
        sent_messages = []

        async def mock_send(message):
            sent_messages.append(message)

        await self.middleware(scope, mock_receive, mock_send)

        # User should be None
        assert scope["state"]["user"] is None
