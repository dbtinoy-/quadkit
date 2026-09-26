"""Backend factory helpers for Quadkit Cache provider.

This module contains a single, focused factory that creates concrete
backend instances from a `CacheBackendConfig`. Keeping backend creation
logic here makes `provider.py` smaller and easier to test.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.cache.backends.memcached import MemcachedCacheBackend
from quadkit.cache.backends.memory import MemoryCacheBackend
from quadkit.cache.backends.redis import RedisCacheBackend
from quadkit.cache.config import (
    CacheBackendConfig,
    default_cache_config,
    resolve_backend_type,
)
from quadkit.cache.types import BackendType

if TYPE_CHECKING:
    from quadkit.contracts import CacheBackendProtocol
    from quadkit.contracts.core import HookRegistryProtocol


async def create_backend(
    config: CacheBackendConfig,
    container: Any | None = None,
    hooks: HookRegistryProtocol | None = None,
) -> CacheBackendProtocol:
    """Create a backend instance from a CacheBackendConfig.

    This helper mirrors the previous logic found inside
    `CacheProvider._create_backend` but is easier to unit test in
    isolation.

    Args:
        config: Backend configuration.
        container: DI container for resolving dependencies.
        hooks: Optional hook registry.
    """
    cache_config = default_cache_config()
    if config.default_ttl is not None:
        cache_config.default_ttl = config.default_ttl
    cache_config.key_prefix = config.key_prefix
    cache_config.enable_metrics = getattr(config, "enable_metrics", True)

    if resolve_backend_type(config) == BackendType.MEMORY:
        return MemoryCacheBackend(
            config=cache_config,
            max_size=config.max_size,
            hooks=hooks,
        )

    if resolve_backend_type(config) == BackendType.REDIS:
        if not config.redis_url:
            raise ValueError("Redis backend requires a redis_url")

        # StateStoreProtocol should be registered by the cache provider
        if not container:
            raise ValueError("Container required for Redis backend creation")

        try:
            # Look for a StateStoreProtocol registered with a name matching the backend.
            # bypass_visibility=True: string keys aren't in the module graph — this is
            # a framework-internal lookup, not a cross-module dependency.
            state_store = await container.resolve(
                f"state_store.{config.name}", bypass_visibility=True
            )
        except (AttributeError, TypeError, RuntimeError, LookupError, ValueError):
            raise ValueError(
                f"No StateStoreProtocol found for Redis backend '{config.name}'. "
                "This should be registered automatically by CacheProvider.",
            ) from None

        return RedisCacheBackend(store=state_store, config=cache_config, hooks=hooks)

    if resolve_backend_type(config) == BackendType.MEMCACHED:
        return MemcachedCacheBackend(
            servers=config.memcached_servers or [],
            config=cache_config,
        )

    raise ValueError(f"Unsupported backend type: {resolve_backend_type(config)}")


__all__ = ["create_backend"]
