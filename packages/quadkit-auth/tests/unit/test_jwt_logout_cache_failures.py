from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr

from quadkit.auth.authn.core import User
from quadkit.auth.authn.jwt import JWTTokenManager


@pytest.mark.asyncio
async def test_logout_uses_in_memory_fallback_when_cache_missing():
    """Test that logout falls back to in-memory blacklist when no cache is configured."""
    manager = JWTTokenManager(
        current_key_id="default", keys={"default": SecretStr("secret_key_at_least_32_bytes_long_for_tests")}, cache_service=None,
    )
    user = User(user_id="u1", name="u", email="u@example.com")
    token = manager.create_access_token(user)

    # Should succeed using the in-memory fallback, not raise RuntimeError
    result = await manager.logout(token)
    assert result.is_ok()


@pytest.mark.asyncio
async def test_logout_returns_false_when_cache_set_raises():
    cache = MagicMock()

    async def set_raise(key, value, ttl=None):
        raise RuntimeError("cache write failure")

    cache.set = MagicMock(side_effect=set_raise)

    manager = JWTTokenManager(
        current_key_id="default", keys={"default": SecretStr("secret_key_at_least_32_bytes_long_for_tests")}, cache_service=cache,
    )
    user = User(user_id="u2", name="u2", email="u2@example.com")
    token = manager.create_access_token(user)

    with pytest.raises(RuntimeError, match="cache write failure"):
        await manager.logout(token)


@pytest.mark.asyncio
async def test_logout_all_user_tokens_raises_runtime_error_when_cache_missing():
    manager = JWTTokenManager(
        current_key_id="default", keys={"default": SecretStr("secret_key_at_least_32_bytes_long_for_tests")}, cache_service=None,
    )
    with pytest.raises(RuntimeError, match="no cache backend configured"):
        await manager.logout_all_user_tokens("u3")


@pytest.mark.asyncio
async def test_logout_all_user_tokens_returns_false_when_cache_set_raises():
    cache = MagicMock()

    async def set_raise(key, value, ttl=None):
        raise RuntimeError("cache write failure")

    cache.set = MagicMock(side_effect=set_raise)

    manager = JWTTokenManager(
        current_key_id="default", keys={"default": SecretStr("secret_key_at_least_32_bytes_long_for_tests")}, cache_service=cache,
    )
    with pytest.raises(RuntimeError, match="cache write failure"):
        await manager.logout_all_user_tokens("u4")
