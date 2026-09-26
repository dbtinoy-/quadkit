import asyncio

import pytest

from quadkit.cache.backends.memcached.backend import MemcachedCacheBackend


@pytest.mark.asyncio
async def test_client_attribute_takes_precedence_and_does_not_hang():
    """Ensure that setting backend._client is honored and avoids awaiting a patched _get_client() that returns a pending Future."""
    backend = MemcachedCacheBackend(servers=["localhost:11211"])

    # Patch _get_client to return an unresolved Future (simulates a misbehaving monkeypatch)
    backend._get_client = lambda: asyncio.Future()

    class FakeClient:
        async def get(self, key: str):
            raise RuntimeError("simulated backend error")

    # Set the client attribute directly; get() should use this and not hang on the unresolved Future
    backend._client = FakeClient()

    # Should return None (error handled) and complete promptly
    result = await asyncio.wait_for(backend.get("some-key"), timeout=1)
    assert result is None
