"""
Quadkit Cache - Multi-backend caching system for Quadkit Framework.

This package provides a unified caching API across multiple backends including
in-memory, Redis, and Memcached. It follows the Quadkit Framework's provider
pattern for clean integration and extensibility.

Exports:
    CacheService: Main cache service for DI injection
    CacheProvider: Provider for framework integration
    CacheConfig: Configuration model
    CacheBackendProtocol: Protocol for backend implementations
    BackendType: Enum of supported backends
    CacheError: Base exception for cache errors
"""

from __future__ import annotations

import importlib.metadata

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from typing import TYPE_CHECKING, Any

from quadkit.cache.constants import __version__ as __version__

if TYPE_CHECKING:
    from quadkit.cache.backends.memcached.backend import MemcachedCacheBackend
    from quadkit.cache.backends.memory.backend import MemoryCacheBackend
    from quadkit.cache.backends.redis.backend import RedisCacheBackend
    from quadkit.cache.config import (
        CacheBackendConfig,
        CacheConfig,
        CacheOperationConfig,
        CacheServiceConfig,
        EnvironmentConfigLoader,
        MemcachedBackendConfig,
        MemoryBackendConfig,
        RedisBackendConfig,
    )
    from quadkit.cache.decorators import cacheable
    from quadkit.cache.di.provider import CacheProvider
    from quadkit.cache.exceptions import (
        CacheBackendError,
        CacheCapacityError,
        CacheConfigurationError,
        CacheConnectionError,
        CacheError,
        CacheInvalidationError,
        CacheKeyError,
        CacheSerializationError,
        CacheStampedeError,
        CacheTimeoutError,
    )
    from quadkit.cache.serialization.compression import CompressingSerializer
    from quadkit.cache.serialization.json import JSONSerializer
    from quadkit.cache.serialization.type_registry import (
        DEFAULT_REGISTRY,
        TypeRegistry,
    )
    from quadkit.cache.service.core import CacheService
    from quadkit.cache.service.decorators import (
        CacheDecorator,
        cache,
        conditional_cache,
        invalidate_cache,
        remember,
    )
    from quadkit.cache.service.request_cache import (
        cache_in_request,
        clear_request_cache,
        get_request_cache,
    )
    from quadkit.cache.stores import RedisLockStore, RedisSecretStore, RedisStateStore
    from quadkit.cache.stores.redis_state import RedisDriver
    from quadkit.cache.types import (
        BackendType,
        CacheEntry,
        CacheHealthResult,
        CacheItem,
        CacheMetrics,
        CacheResult,
        CacheStats,
        CacheStatus,
        CacheStatusHandler,
        DistributedLockInfo,
        TaggedCacheKey,
    )
    from quadkit.contracts.core import HealthStatus
    from quadkit.contracts.infra.cache import (
        AsyncStringSerializerProtocol,
        CacheAdminProtocol,
        CacheBackendProtocol,
        CacheHealthCheckerProtocol,
        CacheKeyBuilderProtocol,
        CacheProtectionStrategyProtocol,
    )

_LAZY_IMPORTS = {
    "AutoRenewingLock": "quadkit.cache.locks.auto_renewing",
    "BackendType": "quadkit.cache.types",
    "cacheable": "quadkit.cache.decorators",
    "cache_in_request": "quadkit.cache.service.request_cache",
    "clear_request_cache": "quadkit.cache.service.request_cache",
    "get_request_cache": "quadkit.cache.service.request_cache",
    "CacheAdminProtocol": "quadkit.contracts.infra.cache",
    "CacheBackendProtocol": "quadkit.contracts.infra.cache",
    "CacheBackendConfig": "quadkit.cache.config",
    "CacheBackendError": "quadkit.cache.exceptions",
    "CacheCapacityError": "quadkit.cache.exceptions",
    "CacheConfig": "quadkit.cache.config",
    "CacheConfigurationError": "quadkit.cache.exceptions",
    "CacheConnectionError": "quadkit.cache.exceptions",
    "CacheDecorator": "quadkit.cache.service.decorators",
    "CacheEntry": "quadkit.cache.types",
    "CacheError": "quadkit.cache.exceptions",
    "CacheHealthCheckerProtocol": "quadkit.contracts.infra.cache",
    "CacheHealthResult": "quadkit.cache.types",
    "CacheInvalidationError": "quadkit.cache.exceptions",
    "CacheItem": "quadkit.cache.types",
    "CacheKeyBuilderProtocol": "quadkit.contracts.infra.cache",
    "CacheKeyError": "quadkit.cache.exceptions",
    "CacheMetrics": "quadkit.cache.types",
    "CacheModule": "quadkit.cache.module",
    "CacheOperationConfig": "quadkit.cache.config",
    "CacheProtectionStrategyProtocol": "quadkit.contracts.infra.cache",
    "CacheProvider": "quadkit.cache.di.provider",
    "CacheResult": "quadkit.cache.types",
    "CacheSerializationError": "quadkit.cache.exceptions",
    "CacheService": "quadkit.cache.service.core",
    "CacheServiceConfig": "quadkit.cache.config",
    "CacheStampedeError": "quadkit.cache.exceptions",
    "CacheStats": "quadkit.cache.types",
    "CacheStatus": "quadkit.cache.types",
    "CacheStatusHandler": "quadkit.cache.types",
    "CacheTimeoutError": "quadkit.cache.exceptions",
    "DistributedLockInfo": "quadkit.cache.types",
    "CompressingSerializer": "quadkit.cache.serialization.compression",
    "CostAwareCacheDecision": "quadkit.cache.semantic.cost_decision",
    "DEFAULT_REGISTRY": "quadkit.cache.serialization.type_registry",
    "EnvironmentConfigLoader": "quadkit.cache.config",
    "FaissVectorIndex": "quadkit.cache.semantic.vector_index",
    "HealthStatus": "quadkit.contracts.core",
    "JSONSerializer": "quadkit.cache.serialization.json",
    "MemcachedBackendConfig": "quadkit.cache.config",
    "MemcachedCacheBackend": "quadkit.cache.backends.memcached.backend",
    "MemoryBackendConfig": "quadkit.cache.config",
    "MemoryCacheBackend": "quadkit.cache.backends.memory.backend",
    "RedisBackendConfig": "quadkit.cache.config",
    "RedisCacheBackend": "quadkit.cache.backends.redis.backend",
    "AsyncStringSerializerProtocol": "quadkit.contracts.infra.cache",
    "SemanticCacheStore": "quadkit.cache.semantic.store",
    "TaggedCacheKey": "quadkit.cache.types",
    "TypeRegistry": "quadkit.cache.serialization.type_registry",
    "cache": "quadkit.cache.service.decorators",
    "conditional_cache": "quadkit.cache.service.decorators",
    "invalidate_cache": "quadkit.cache.service.decorators",
    "remember": "quadkit.cache.service.decorators",
    "RedisDriver": "quadkit.cache.stores.redis_state",
    "RedisLockStore": "quadkit.cache.stores.redis_lock",
    "RedisSecretStore": "quadkit.cache.stores.redis_secrets",
    "RedisStateStore": "quadkit.cache.stores.redis_state",
    # Hooks
    "CacheConnectedHook": "quadkit.cache.hooks",
    "CacheDisconnectedHook": "quadkit.cache.hooks",
    "CacheEntryEvictedHook": "quadkit.cache.hooks",
    # Events
    "CacheHitEvent": "quadkit.cache.events",
    "CacheMissEvent": "quadkit.cache.events",
    "CacheEvictedEvent": "quadkit.cache.events",
    "CacheConnectedEvent": "quadkit.cache.events",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        import importlib

        module_path = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> Any:
    return sorted(set(__all__) | set(_LAZY_IMPORTS.keys()))


__all__ = list(_LAZY_IMPORTS.keys())
