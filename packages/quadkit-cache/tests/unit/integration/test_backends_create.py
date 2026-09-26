from unittest.mock import AsyncMock

import pytest

from quadkit.cache.backends.factory import create_backend
from quadkit.cache.backends.memcached import MemcachedCacheBackend
from quadkit.cache.backends.memory import MemoryCacheBackend
from quadkit.cache.backends.redis import RedisCacheBackend
from quadkit.cache.config import CacheBackendConfig
from quadkit.cache.types import BackendType
from quadkit.hooks import HookRegistry


@pytest.mark.asyncio
async def test_create_memory_backend() -> None:
    cfg = CacheBackendConfig.model_validate({"name": "mem", "type": BackendType.MEMORY})
    backend = await create_backend(cfg)
    assert isinstance(backend, MemoryCacheBackend)


@pytest.mark.asyncio
async def test_create_memory_backend_passes_hook_registry() -> None:
    cfg = CacheBackendConfig.model_validate({"name": "mem", "type": BackendType.MEMORY})
    hooks = HookRegistry("cache-test")

    backend = await create_backend(cfg, hooks=hooks)

    assert isinstance(backend, MemoryCacheBackend)
    assert backend._hooks is hooks


@pytest.mark.asyncio
async def test_create_redis_requires_url_and_success() -> None:
    # Use default config which should provide a default redis_url
    cfg_default = CacheBackendConfig.model_validate(
        {"name": "redis1", "type": BackendType.REDIS},
    )
    container = AsyncMock()
    container.resolve.return_value = AsyncMock()
    backend = await create_backend(cfg_default, container=container)
    assert isinstance(backend, RedisCacheBackend)

    cfg_ok = CacheBackendConfig.model_validate(
        {
            "name": "redis2",
            "type": BackendType.REDIS,
            "redis_url": "redis://localhost:6379/1",
        },
    )
    backend = await create_backend(cfg_ok, container=container)
    assert isinstance(backend, RedisCacheBackend)


@pytest.mark.asyncio
async def test_create_redis_backend_passes_hook_registry() -> None:
    cfg = CacheBackendConfig.model_validate(
        {
            "name": "redis1",
            "type": BackendType.REDIS,
            "redis_url": "redis://localhost:6379/1",
        },
    )
    hooks = HookRegistry("cache-test")
    container = AsyncMock()
    container.resolve.return_value = AsyncMock()

    backend = await create_backend(cfg, container=container, hooks=hooks)

    assert isinstance(backend, RedisCacheBackend)
    assert backend._hooks is hooks


@pytest.mark.asyncio
async def test_create_memcached_backend_servers() -> None:
    cfg = CacheBackendConfig.model_validate(
        {
            "name": "mc",
            "type": BackendType.MEMCACHED,
            "memcached_servers": ["localhost:11211"],
        },
    )
    backend = await create_backend(cfg)
    assert isinstance(backend, MemcachedCacheBackend)
