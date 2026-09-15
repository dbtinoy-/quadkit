"""Cache protocol class definitions.

Protocol classes for caching backends and related utilities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from quadkit.contracts.core import HealthCheckResult, ProviderProtocol

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.core.result import Result
    from quadkit.contracts.infra.cache.exceptions import CacheError


@runtime_checkable
class CacheBackendProtocol(Protocol):
    """Protocol for cache backend implementations.

    This interface defines the contract that all cache backend implementations
    must follow. It provides a unified API for different storage mechanisms
    (memory, Redis, Memcached, etc.).

    Example:
        ```python
        class RedisBackend:
            async def get(self, key: str) -> Result[Any | None, CacheError]:
                try:
                    data = await self._redis.get(key)
                    return Ok(self._serializer.deserialize(data) if data else None)
                except Exception as exc:
                    return Err(CacheError(str(exc)))

            async def set(
                self, key: str, value: Any, ttl: int | None = None
            ) -> Result[None, CacheError]:
                try:
                    data = self._serializer.serialize(value)
                    await self._redis.set(key, data, ex=ttl)
                    return Ok(None)
                except Exception as exc:
                    return Err(CacheError(str(exc)))
        ```
    """

    async def get(self, key: str) -> Result[Any | None, CacheError]:
        """Get a value from the cache.

        Args:
            key: The cache key to retrieve.

        Returns:
            Ok(value) if found, Ok(None) if not found, Err(CacheError) on failure.

        Note:
            The return type is ``Any`` by design: the cache is a
            heterogeneous store and the caller knows the expected type.
            Use ``cast(T, result.unwrap())`` at call sites for type safety.
        """
        ...

    async def set(
        self, key: str, value: Any, ttl: int | None = None
    ) -> Result[None, CacheError]:
        """Set a value in the cache with optional TTL.

        Args:
            key: The cache key to set.
            value: The value to cache.
            ttl: Time to live in seconds (optional).

        Returns:
            Ok(None) if successful, Err(CacheError) on failure.
        """
        ...

    async def delete(self, key: str) -> Result[bool, CacheError]:
        """Delete a value from the cache.

        Args:
            key: The cache key to delete.

        Returns:
            Ok(True) if deleted, Ok(False) if not found, Err(CacheError) on failure.
        """
        ...

    async def delete_many(self, keys: list[str]) -> Result[int, CacheError]:
        """Delete multiple values from the cache.

        Args:
            keys: List of cache keys to delete.

        Returns:
            Ok(count) of deleted keys, Err(CacheError) on failure.
        """
        ...

    async def delete_pattern(self, pattern: str) -> Result[int, CacheError]:
        """Delete all keys matching a glob-style pattern.

        Args:
            pattern: Glob pattern (e.g. ``"pet:list:*"``).  Supports ``*``
                as a wildcard matching any sequence of characters.

        Returns:
            Ok(count) of deleted keys, Err(CacheError) on failure.
        """
        ...

    async def exists(self, key: str) -> Result[bool, CacheError]:
        """Check if a key exists in the cache.

        Args:
            key: The cache key to check.

        Returns:
            Ok(True) if exists, Ok(False) otherwise, Err(CacheError) on failure.
        """
        ...

    async def clear(self) -> Result[None, CacheError]:
        """Clear all values from the cache.

        Returns:
            Ok(None) if successful, Err(CacheError) on failure.
        """
        ...

    async def get_many(self, keys: list[str]) -> Result[dict[str, Any], CacheError]:
        """Get multiple values from the cache.

        Args:
            keys: List of cache keys to retrieve.

        Returns:
            Ok(dict) mapping found keys to values, Err(CacheError) on failure.
        """
        ...

    async def set_many(
        self, items: dict[str, Any], ttl: int | None = None
    ) -> Result[None, CacheError]:
        """Set multiple values in the cache.

        Args:
            items: Dictionary of key-value pairs to cache.
            ttl: Time to live in seconds for all items.

        Returns:
            Ok(None) if all items set successfully, Err(CacheError) on failure.
        """
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform a health check on the cache backend.

        Returns:
            Structured HealthCheckResult.
        """
        ...


@runtime_checkable
class CacheProtectionStrategyProtocol(Protocol):
    """Protocol for cache stampede protection strategies."""

    async def acquire_lock(self, key: str, ttl: int) -> bool:
        """Attempt to acquire a lock for cache population.

        Args:
            key: Cache key to lock.
            ttl: Lock TTL in seconds.

        Returns:
            True if lock was acquired.
        """
        ...

    async def release_lock(self, key: str) -> bool:
        """Release a previously acquired lock.

        Args:
            key: Cache key to unlock.

        Returns:
            True if released successfully.
        """
        ...

    async def wait_for_value(
        self,
        key: str,
        timeout: float,
        check_interval: float = 0.1,
    ) -> Any | None:
        """Wait for a value to be populated.

        Args:
            key: Cache key to wait for.
            timeout: Maximum wait time in seconds.
            check_interval: Check interval in seconds.

        Returns:
            Cached value if found, None if timeout.
        """
        ...


@runtime_checkable
class CacheKeyBuilderProtocol(Protocol):
    """Protocol for building cache keys from function arguments."""

    def build_key(
        self,
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        prefix: str | None = None,
    ) -> str:
        """Build a cache key from function call information.

        Args:
            func: Function being cached.
            args: Positional arguments.
            kwargs: Keyword arguments.
            prefix: Optional key prefix.

        Returns:
            Unique cache key string.
        """
        ...


@runtime_checkable
class CacheHealthCheckerProtocol(Protocol):
    """Protocol for cache health checking."""

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform a health check on the cache.

        Returns:
            Structured HealthCheckResult.
        """
        ...


@runtime_checkable
class CacheProviderProtocol(ProviderProtocol, Protocol):
    """Protocol for cache providers.

    Cache providers are responsible for setting up caching backends,
    cache warming, and cache management.
    """


__all__ = [
    "CacheBackendProtocol",
    "CacheHealthCheckerProtocol",
    "CacheKeyBuilderProtocol",
    "CacheProtectionStrategyProtocol",
    "CacheProviderProtocol",
]
