from __future__ import annotations

"""Redis CacheBackend compliance test using a real Redis connection."""

import pytest

from quadkit.testing.compliance import CacheBackendCompliance

pytestmark = [pytest.mark.integration, pytest.mark.requires_redis]


class TestRedisCacheCompliance(CacheBackendCompliance):
    """Verify RedisCacheBackend satisfies CacheBackendCompliance."""

    @pytest.fixture(autouse=True)
    async def _setup(self, redis_client: object) -> None:
        """Capture the live redis_client fixture."""
        self._redis_client = redis_client

    async def create_backend(self) -> object:
        """Create RedisCacheBackend using the real Redis StateStore."""
        try:
            from quadkit.cache.backends.redis.backend import RedisCacheBackend
        except ImportError:
            pytest.skip("RedisCacheBackend not available")

        pytest.skip("TODO: wrap redis_client in StateStoreProtocol adapter before instantiating RedisCacheBackend")
