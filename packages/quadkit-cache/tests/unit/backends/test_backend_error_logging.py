import asyncio
from unittest.mock import patch

import pytest

from quadkit.cache.backends.memcached.backend import MemcachedCacheBackend
from quadkit.cache.backends.memory.backend import MemoryCacheBackend
from quadkit.cache.backends.redis.backend import RedisCacheBackend
import quadkit.cache.backends.redis.backend as redis_backend_module
import quadkit.cache.backends.memcached.backend as memcached_backend_module
import quadkit.cache.backends.memory.backend as memory_backend_module


@pytest.mark.asyncio
async def test_redis_get_logs_and_increments_errors():
    class MockStore:
        async def get(self, key):
            raise RuntimeError("boom")
    
    backend = RedisCacheBackend(store=MockStore())

    with patch.object(redis_backend_module, "logger") as mock_log:
        result = await backend.get("key")
        assert result.is_err()
        assert backend._metrics.errors >= 1
        mock_log.warning.assert_called()
        assert "Redis get failed" in mock_log.warning.call_args[0][0]


@pytest.mark.asyncio
async def test_memcached_get_logs_and_increments_errors():
    backend = MemcachedCacheBackend(servers=["localhost:11211"])

    async def raise_get(prefixed_key):
        raise RuntimeError("boom")

    backend._get_client = lambda: asyncio.Future()

    # Provide a fake client via _client attribute
    class FakeClient:
        async def get(self, k):
            raise RuntimeError("boom")

    backend._client = FakeClient()  # type: ignore[attr-defined]

    with patch.object(memcached_backend_module, "logger") as mock_log:
        result = await backend.get("key")
        assert result is None
        assert backend._metrics.errors >= 1
        mock_log.warning.assert_called()
        assert "Memcached get failed" in mock_log.warning.call_args[0][0]


@pytest.mark.asyncio
async def test_memory_get_logs_and_increments_errors():
    backend = MemoryCacheBackend()

    async def raise_get(prefixed_key):
        raise RuntimeError("boom")

    backend._store.get = raise_get  # type: ignore[attr-defined]

    with patch.object(memory_backend_module, "logger") as mock_log:
        result = await backend.get("key")
        assert result.is_err()
        assert backend._metrics.errors >= 1
        mock_log.warning.assert_called()
        assert "Memory get failed" in mock_log.warning.call_args[0][0]
