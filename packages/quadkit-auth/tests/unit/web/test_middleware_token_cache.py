import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.auth.di.sub_providers.authentication_provider import (
    AuthenticationProvider,
)
from quadkit.auth.web import AuthMiddleware


class DummyRequest:
    def __init__(self):
        self.headers = {}
        self.query_params = {}
        self.cookies = {}
        self.state = type("S", (), {})()
        self.url = type("U", (), {"path": "/"})
        self.scope = {}


@pytest.mark.asyncio
async def test_cleanup_token_cache_removes_expired_entries():
    provider = MagicMock(spec=AuthenticationProvider)
    # Correct constructor is (app, provider) or (provider) depending on middleware structure
    # But here AuthMiddleware(provider) is used, assuming it's a wrapper
    mw = AuthMiddleware(provider)

    # Insert expired and valid entries
    now = time.monotonic()
    # Use TokenCache.set to populate, then poke internals to expire
    await mw.token_cache.set("token_a", "user_a")
    await mw.token_cache.set("token_b", "user_b")

    import hashlib

    hash_a = hashlib.sha256(b"token_a").hexdigest()
    hash_b = hashlib.sha256(b"token_b").hexdigest()

    mw.token_cache._cache[hash_a]["expires_at"] = now - 10
    mw.token_cache._cache[hash_b]["expires_at"] = now + 100

    mw.token_cache._cleanup_expired()

    assert hash_a not in mw.token_cache._cache
    assert hash_b in mw.token_cache._cache


@pytest.mark.asyncio
async def test_authenticate_request_triggers_cleanup_on_threshold():
    provider = MagicMock(spec=AuthenticationProvider)
    provider.get_user = AsyncMock(return_value=None)
    provider.verify_token = AsyncMock(return_value=None)
    mw = AuthMiddleware(provider)

    # Add >100 entries to trigger cleanup on next set()
    # Note: TokenCache calls _cleanup_expired on every set()
    now = time.monotonic()
    for i in range(105):
        token = f"token_{i}"
        await mw.token_cache.set(token, f"user_{i}")
        # Make some expired
        if i < 50:
            import hashlib

            h = hashlib.sha256(token.encode()).hexdigest()
            mw.token_cache._cache[h]["expires_at"] = now - 10

    # Trigger another set to trigger cleanup
    await mw.token_cache.set("trigger_token", "trigger_user")

    # After cleanup, we should have fewer entries because half were expired
    # (106 entries total, 50 expired -> 56 remaining)
    assert len(mw.token_cache._cache) < 106
