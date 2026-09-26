from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from quadkit.auth.authn.core import User
from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.exceptions import TokenBlacklistedError


@pytest.mark.asyncio
async def test_blacklist_fail_closed_when_cache_raises():
    # Create token manager with a mock cache that raises on exists
    cache = MagicMock()

    async def exists_raise(key):
        raise RuntimeError("cache down")

    cache.exists = MagicMock(side_effect=exists_raise)

    manager = JWTTokenManager(
        current_key_id="default", keys={"default": SecretStr("secret_key_at_least_32_bytes_long_for_tests")}, cache_service=cache,
    )

    user = User(user_id="u1", name="u", email="u@example.com")
    token = manager.create_access_token(user)

    # _is_token_blacklisted catches RuntimeError and returns True (fail closed)
    # verify_token then returns Err(TokenBlacklistedError)
    result = await manager.verify_token(token)
    assert result.is_err()
    assert isinstance(result.unwrap_err(), TokenBlacklistedError)

@pytest.mark.asyncio
async def test_in_memory_blacklist_fallback_when_no_cache():
    """Test that token blacklisting uses in-memory fallback when no cache is configured."""
    manager = JWTTokenManager(
        current_key_id="default", keys={"default": SecretStr("secret_key_at_least_32_bytes_long_for_tests")}, cache_service=None,
    )

    user = User(user_id="u1", name="u", email="u@example.com")
    token = manager.create_access_token(user)

    # Token should be valid before blacklisting
    result = await manager.verify_token(token)
    assert result.is_ok()

    # Blacklist using in-memory fallback — must not raise
    logout_result = await manager.logout(token)
    assert logout_result.is_ok()

    # Token must now be rejected as blacklisted
    from quadkit.auth.exceptions import TokenBlacklistedError

    result = await manager.verify_token(token)
    assert result.is_err()
    assert isinstance(result.unwrap_err(), TokenBlacklistedError)
