"""Unit tests for RateLimitConfig.storage_backend and RateLimitProvider cache fallback."""

from __future__ import annotations

from quadkit.cache.backends.memory import MemoryCacheBackend
from quadkit.contracts.infra.cache import CacheBackendProtocol
from quadkit.di.container import Container
from quadkit.web.config.rate_limit import RateLimitConfig
from quadkit.web.di.rate_limit import RateLimitProvider


async def test_rate_limit_config_storage_backend_and_provider_cache_fallback() -> None:
    """RateLimitConfig validates storage_backend and RateLimitProvider falls back to CacheBackendProtocol."""
    cfg = RateLimitConfig(storage_backend="memory")
    assert cfg.storage_backend == "memory"

    mem_cache = MemoryCacheBackend()
    container = Container()
    container.singleton(CacheBackendProtocol, instance=mem_cache)

    provider = RateLimitProvider(backend="redis")
    await provider.register(container)
    container.freeze()
    await provider.boot(container)

    assert provider.limiter is not None
    assert provider.limiter._cache_backend is mem_cache
    await provider.shutdown()
