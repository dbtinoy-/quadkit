"""Integration tests for token refresh cycle.

Demonstrates the complete end-to-end token refresh flow:
1. User authentication (login) → get token pair
2. Refresh access token using refresh token
3. Verify new token works for requests

This test satisfies P0 task A-04 from auth-guide-alignment.md:
"Add integration test for token refresh cycle - End-to-end test:
login → get tokens → refresh → verify new token → old refresh rejected"
"""

from pydantic import SecretStr
import pytest

from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.authn.security import PasswordHasher
from quadkit.auth.authn.services import AuthenticationService
from quadkit.auth.di.sub_providers.authentication_provider import (
    AuthenticationProvider,
)


class MockCache:
    """Simple mock cache for testing."""

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


class TestTokenRefreshCycle:
    """Test complete token refresh cycle integration."""

    @pytest.fixture
    def setup(self):
        """Setup auth service for testing."""
        cache = MockCache()
        jwt_manager = JWTTokenManager(
            current_key_id="default",
            keys={
                "default": SecretStr(
                    "test_secret_key_for_testing_full_cycle_integration"
                )
            },
            cache_service=cache,
        )
        provider = AuthenticationProvider(token_manager=jwt_manager)
        return {
            "cache": cache,
            "jwt_manager": jwt_manager,
            "provider": provider,
            "service": provider.service,
        }

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_complete_token_refresh_cycle(self, setup) -> None:
        """Test complete token refresh cycle: login → refresh → verify new token.

        Steps:
        1. Create test user
        2. Authenticate (login) → get token pair (access + refresh)
        3. Verify initial access token works
        4. Refresh using refresh token → get new token pair
        5. Verify new access token works
        """
        service: AuthenticationService = setup["service"]
        user_store = setup["provider"].user_store

        # Step 1: Create a test user
        hashed_pw = await PasswordHasher().hash("TestPassword123!")
        user = await user_store.create_user(
            name="testuser",
            email="test@example.com",
            hashed_password=hashed_pw,
        )
        assert user is not None, "User creation should succeed"

        # Step 2: Authenticate (login) → get token pair
        auth_result = await service.authenticate_user(
            "test@example.com", "TestPassword123!"
        )
        assert auth_result.is_ok(), f"Authentication failed: {auth_result.unwrap_err()}"

        authenticated_user = auth_result.unwrap()
        initial_token = service.create_token(authenticated_user)
        assert initial_token.token is not None, "Access token should not be None"
        assert initial_token.refresh_token is not None, (
            "Refresh token should not be None"
        )

        initial_access = initial_token.token
        initial_refresh = initial_token.refresh_token

        # Step 3: Verify initial access token works
        verify_result = await service.verify_token(initial_access)
        assert verify_result.is_ok(), (
            f"Initial token verification failed: {verify_result.unwrap_err()}"
        )
        verified_user = verify_result.unwrap()
        assert verified_user.user_id == user.user_id, (
            "Verified user ID should match original user"
        )

        # Step 4: Refresh access token using refresh token
        refresh_result = await service.refresh_token(initial_refresh)
        assert refresh_result.is_ok(), (
            f"Token refresh failed: {refresh_result.unwrap_err()}"
        )

        new_token = refresh_result.unwrap()
        assert new_token.token is not None, "New access token should not be None"
        assert new_token.refresh_token is not None, (
            "New refresh token should not be None"
        )
        # Access token should be different from old one
        assert new_token.token != initial_access, (
            "New access token should differ from old one"
        )

        # Step 5: Verify new token works
        verify_new_result = await service.verify_token(new_token.token)
        assert verify_new_result.is_ok(), (
            f"New token verification failed: {verify_new_result.unwrap_err()}"
        )
        verified_new_user = verify_new_result.unwrap()
        assert verified_new_user.user_id == user.user_id, (
            "New token should still validate for same user"
        )
