"""
Memcached cache backend implementation.

This module provides a cache backend for Memcached that follows the same
pattern as other backends, ensuring consistency across the framework.
"""

from __future__ import annotations

import contextlib
from typing import Any

try:
    import pymemcache
    from pymemcache import Client as AsyncMemcachedClient
    from pymemcache.client.base import (
        Client as MemcachedClient,
    )
except ImportError:
    pymemcache = None
    MemcachedClient = None
    AsyncMemcachedClient = None

from quadkit.cache.config import CacheOperationConfig, default_cache_config
from quadkit.cache.types import CacheMetrics
from quadkit.contracts import CacheBackendProtocol
from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.logging import get_logger

logger = get_logger(__name__)


class MemcachedCacheBackend(CacheBackendProtocol):
    """
    Memcached cache backend implementation.

    This backend provides Memcached-based distributed caching with TTL support.
    Unlike memory and Redis backends, this is implemented directly since
    the core infrastructure layer doesn't provide a Memcached driver.
    """

    def __init__(
        self,
        servers: list[str],
        config: CacheOperationConfig | None = None,
    ):
        """
        Initialize the Memcached cache backend.

        Args:
            servers: List of Memcached server addresses (e.g., ["localhost:11211"]).
            config: Cache configuration. If None, uses default configuration.

        Raises:
            ImportError: If pymemcache is not installed.
        """
        # Allow tests to patch or set the underlying client even when the
        # optional dependency is not installed. We don't raise here so unit
        # tests can inject a mock AsyncMemcachedClient via `backend._client`.
        self.config = config or default_cache_config()
        self.servers = servers
        self._servers = servers
        self._client: AsyncMemcachedClient | None = None
        self._metrics = CacheMetrics()

    async def _get_client(self) -> AsyncMemcachedClient:
        """Lazy client initialization."""
        if self._client is None:
            # Use the first server for now - could be enhanced to support multiple
            host, port = self._servers[0].split(":")
            self._client = AsyncMemcachedClient(host, int(port))
        return self._client

    async def get(self, key: str) -> Any | None:  # type: ignore[override]
        """
        Get a value from the cache.

        Args:
            key: The cache key to retrieve.

        Returns:
            The cached value if found and not expired, None otherwise.
        """
        try:
            client = (
                self._client if self._client is not None else await self._get_client()
            )
            prefixed_key = self.config.make_key(key)
            value = await client.get(prefixed_key)

            if value is None:
                await self._metrics.record_miss()
                return None

            await self._metrics.record_hit()
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Memcached get failed for key '%s': %s", key, e)
            return None
        else:
            return value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:  # type: ignore[override]
        """
        Set a value in the cache with optional TTL.

        Args:
            key: The cache key to set.
            value: The value to cache.
            ttl: Time to live in seconds. If None, uses default TTL.

        Returns:
            True if successful, False otherwise.
        """
        try:
            client = (
                self._client if self._client is not None else await self._get_client()
            )
            prefixed_key = self.config.make_key(key)
            effective_ttl = ttl or self.config.default_ttl

            # Memcached expects bytes for values
            if isinstance(value, str):
                value_bytes = value.encode("utf-8")
            elif isinstance(value, (int, float)):
                value_bytes = str(value).encode("utf-8")
            else:
                # For complex objects, we'd need serialization
                # For now, convert to string representation
                value_bytes = str(value).encode("utf-8")

            result = await client.set(
                prefixed_key,
                value_bytes,
                expire=effective_ttl or 0,
            )
            if result:
                await self._metrics.record_set()
            return bool(result)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Memcached set failed for key '%s': %s", key, e)
            return False

    async def delete(self, key: str) -> bool:  # type: ignore[override]
        """
        Delete a value from the cache.

        Args:
            key: The cache key to delete.

        Returns:
            True if the key was deleted, False if it didn't exist or error occurred.
        """
        try:
            client = (
                self._client if self._client is not None else await self._get_client()
            )
            prefixed_key = self.config.make_key(key)
            result = await client.delete(prefixed_key)
            if result:
                await self._metrics.record_delete()
            return bool(result)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Memcached delete failed for key '%s': %s", key, e)
            return False

    async def exists(self, key: str) -> bool:  # type: ignore[override]
        """
        Check if a key exists in the cache.

        Args:
            key: The cache key to check.

        Returns:
            True if the key exists and is not expired, False otherwise.
        """
        try:
            client = (
                self._client if self._client is not None else await self._get_client()
            )
            prefixed_key = self.config.make_key(key)
            value = await client.get(prefixed_key)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Memcached exists check failed for key '%s': %s", key, e)
            return False
        else:
            return value is not None

    async def clear(self) -> bool:  # type: ignore[override]
        """
        Clear all values from the cache.

        Note: This operation is not supported by Memcached protocol.
        Memcached doesn't provide a way to clear all keys.

        Returns:
            False (operation not supported).
        """
        # Memcached doesn't support clearing all keys
        return False

    async def get_many(self, keys: list[str]) -> dict[str, Any]:  # type: ignore[override]
        """
        Get multiple values from the cache.

        Args:
            keys: List of cache keys to retrieve.

        Returns:
            Dictionary mapping keys to their values (missing keys omitted).
        """
        try:
            client = (
                self._client if self._client is not None else await self._get_client()
            )
            prefixed_keys = [self.config.make_key(key) for key in keys]
            result_with_prefixes = await client.get_multi(prefixed_keys)

            # Convert back to original keys
            result = {}
            for prefixed_key, raw_value in result_with_prefixes.items():
                original_key = self.config.strip_prefix(prefixed_key)
                # Decode bytes back to string if needed
                value: str | bytes = raw_value
                if isinstance(raw_value, bytes):
                    with contextlib.suppress(UnicodeDecodeError):
                        value = raw_value.decode("utf-8")
                result[original_key] = value

            # Update metrics
            found_count = len(result)
            total_count = len(keys)
            await self._metrics.record_hit(found_count)
            await self._metrics.record_miss(total_count - found_count)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            self._metrics.errors += 1
            logger.warning("Memcached get_many failed: %s", e)
            return {}
        else:
            return result

    async def set_many(self, items: dict[str, Any], ttl: int | None = None) -> bool:  # type: ignore[override]
        """
        Set multiple values in the cache.

        Args:
            items: Dictionary of key-value pairs to cache.
            ttl: Time to live in seconds for all items.

        Returns:
            True if all items were set successfully, False otherwise.
        """
        try:
            client = (
                self._client if self._client is not None else await self._get_client()
            )
            effective_ttl = ttl or self.config.default_ttl

            # Prepare items for Memcached
            memcached_items = {}
            for key, value in items.items():
                prefixed_key = self.config.make_key(key)
                # Convert to bytes as required by Memcached
                if isinstance(value, str):
                    value_bytes = value.encode("utf-8")
                elif isinstance(value, (int, float)):
                    value_bytes = str(value).encode("utf-8")
                else:
                    value_bytes = str(value).encode("utf-8")
                memcached_items[prefixed_key] = value_bytes

            result = await client.set_multi(memcached_items, expire=effective_ttl or 0)
            success = len(result) == 0
            if success:
                await self._metrics.record_set(len(items))
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Memcached set_many failed: %s", e)
            return False
        else:
            return success

    async def delete_many(self, keys: list[str]) -> bool:  # type: ignore[override]
        """
        Delete multiple values from the cache.

        Args:
            keys: List of cache keys to delete.

        Returns:
            True if all keys were deleted successfully, False otherwise.
        """
        try:
            client = (
                self._client if self._client is not None else await self._get_client()
            )
            prefixed_keys = [self.config.make_key(key) for key in keys]

            # Delete keys one by one (Memcached doesn't have delete_multi)
            all_success = True
            for prefixed_key in prefixed_keys:
                result = await client.delete(prefixed_key)
                if not result:
                    all_success = False

            if all_success:
                await self._metrics.record_delete(len(keys))
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Memcached delete_many failed: %s", e)
            return False
        else:
            return all_success

    async def delete_pattern(self, pattern: str) -> int:  # type: ignore[override]
        """Delete keys matching a pattern.

        Memcached does not natively support key enumeration or pattern matching.
        This method logs a warning and returns 0.  If pattern-based invalidation
        is required, use Redis or the in-memory backend instead.

        Args:
            pattern: Glob pattern (not supported by Memcached).

        Returns:
            Always 0 — Memcached does not support key enumeration.
        """
        logger.warning(
            "delete_pattern is not supported by Memcached (pattern: '%s'). "
            "Use tag-based invalidation or switch to Redis.",
            pattern,
        )
        return 0

    def get_stats(self) -> dict[str, int | float | str] | None:
        """Return counters; Memcached does not expose portable key counts."""
        return {
            "hits": self._metrics.hits,
            "misses": self._metrics.misses,
            "evictions": 0,
            "entries": 0,
        }

    def reset_stats(self) -> None:
        """Reset local counters without deleting Memcached values."""
        self._metrics.reset()

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """
        Perform a health check on the cache backend.

        Returns:
            Structured health check result.
        """
        try:
            client = (
                self._client if self._client is not None else await self._get_client()
            )
            # Try a simple operation to test connectivity
            test_key = f"{self.config.key_prefix}health_check_test"
            test_result = await client.set(test_key, b"test", expire=10)
            if test_result:
                await client.delete(test_key)

            return HealthCheckResult(
                component="cache:memcached",
                status=HealthStatus.HEALTHY,
                details={
                    "backend": "memcached",
                    "servers": self._servers,
                    "metrics": await self._metrics.to_dict(),
                    "config": {
                        "default_ttl": self.config.default_ttl,
                        "key_prefix": self.config.key_prefix,
                    },
                },
            )
        except Exception as e:
            logger.exception("Memcached health check failed")
            return HealthCheckResult(
                component="cache:memcached",
                status=HealthStatus.UNHEALTHY,
                error=str(e),
                details={
                    "backend": "memcached",
                    "servers": self._servers,
                    "metrics": await self._metrics.to_dict(),
                },
            )
