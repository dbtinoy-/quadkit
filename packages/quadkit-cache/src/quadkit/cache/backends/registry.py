"""Cache backend registry for extensible cache backends."""

from __future__ import annotations

from typing import Any, Protocol

from quadkit.cache import constants as const
from quadkit.cache.backends.memcached.backend import MemcachedCacheBackend
from quadkit.cache.backends.memory.backend import MemoryCacheBackend
from quadkit.cache.backends.redis.backend import RedisCacheBackend
from quadkit.primitives.registry import BackendRegistry as _CoreBackendRegistry

_REDIS_AVAILABLE = True
_MEMCACHED_AVAILABLE = True


class CacheBackendRegistry(Protocol):
    """Protocol for cache backend factories."""

    def can_create(self, backend_type: str) -> bool:
        """Check if this factory can create the requested backend type."""
        ...

    def create_backend(self, **kwargs: Any) -> Any:
        """Create a backend instance with the given configuration."""
        ...


class MemoryBackendRegistry:
    """Registry for memory cache backend."""

    def can_create(self, backend_type: str) -> bool:
        return backend_type == const.BACKEND_TYPE_MEMORY

    def create_backend(self, **kwargs: Any) -> Any:
        return MemoryCacheBackend(**kwargs)


class RedisBackendRegistry:
    """Registry for Redis cache backend."""

    def can_create(self, backend_type: str) -> bool:
        return backend_type == const.BACKEND_TYPE_REDIS

    def create_backend(self, **kwargs: Any) -> Any:
        if not _REDIS_AVAILABLE:
            raise ImportError(const.ERROR_MSG_REDIS_INSTALL)
        return RedisCacheBackend(**kwargs)


class MemcachedBackendRegistry:
    """Registry for Memcached cache backend."""

    def can_create(self, backend_type: str) -> bool:
        return backend_type == const.BACKEND_TYPE_MEMCACHED

    def create_backend(self, **kwargs: Any) -> Any:
        if not _MEMCACHED_AVAILABLE:
            raise ImportError(const.ERROR_MSG_MEMCACHED_INSTALL)
        return MemcachedCacheBackend(**kwargs)


class BackendRegistry(_CoreBackendRegistry):
    """Central registry for all cache backends.

    Extends :class:`quadkit.primitives.registry.BackendRegistry` so that all
    backend registries share a common hierarchy.  Factory instances are
    stored under their backend-type string key (e.g. ``"redis"``,
    ``"memory"``).

    Example::

        registry = BackendRegistry.with_defaults()
        # Third-party extension:
        registry.register("elasticache", MyElastiCacheFactory())
    """

    def __init__(self) -> None:
        """Initialise an empty registry (populate via ``with_defaults()``)."""
        super().__init__(name="cache.backends")

    @classmethod
    def _default_entries(cls) -> dict[str, CacheBackendRegistry]:
        """Declare the built-in backend factories under type-string keys."""
        return {
            const.BACKEND_TYPE_MEMORY: MemoryBackendRegistry(),
            const.BACKEND_TYPE_REDIS: RedisBackendRegistry(),
            const.BACKEND_TYPE_MEMCACHED: MemcachedBackendRegistry(),
        }

    def register(  # type: ignore[override]
        self,
        registry_or_key: CacheBackendRegistry | str,
        value: Any = None,
    ) -> None:
        """Register a backend factory.

        Supports both the legacy single-argument form
        ``register(factory_instance)`` (key is inferred via ``can_create``)
        and the new two-argument form ``register(key, factory_instance)``
        used by entry-point discovery.

        Args:
            registry_or_key: A factory instance *or* a string key.
            value: The factory when *registry_or_key* is a string key.

        Raises:
            ValueError: If the key cannot be inferred from a factory instance.
        """
        if isinstance(registry_or_key, str):
            super().register(registry_or_key, value)
        else:
            factory = registry_or_key
            for bt in [
                const.BACKEND_TYPE_MEMORY,
                const.BACKEND_TYPE_REDIS,
                const.BACKEND_TYPE_MEMCACHED,
            ]:
                if factory.can_create(bt):
                    super().register(bt, factory)
                    return
            raise ValueError(
                f"Cannot infer backend type key from factory {factory!r}; "
                "use register(key, factory) instead."
            )

    def get_backend(self, backend_type: str, **kwargs: Any) -> Any:
        """Return a backend instance for *backend_type*.

        Args:
            backend_type: Registered type string (``"redis"``, ``"memory"``…).
            **kwargs: Forwarded to the factory's ``create_backend`` method.

        Returns:
            A new backend instance.

        Raises:
            ValueError: If *backend_type* is not registered.
        """
        factory = self.get(backend_type)
        if factory is None:
            available = sorted(self.keys())
            raise ValueError(
                f"Unknown cache backend: {backend_type!r}. Available: {available}"
            )
        return factory.create_backend(**kwargs)


__all__ = [
    "BackendRegistry",
    "CacheBackendRegistry",
]
