"""
Memory cache backend implementation using quadkit-components.

This module provides a cache backend that wraps the MemoryStateStore
from quadkit-components, ensuring DRY compliance and consistency.
"""

from __future__ import annotations

import fnmatch
from typing import Any

from quadkit.cache.backends.memory_state import MemoryStateStore
from quadkit.cache.config import CacheOperationConfig, default_cache_config
from quadkit.cache.hooks import CacheEntryEvictedHook, CacheHitHook, CacheMissHook
from quadkit.cache.types import CacheMetrics
from quadkit.contracts import CacheBackendProtocol
from quadkit.contracts.core import (
    HealthCheckResult,
    HealthStatus,
    HookRegistryProtocol,
)
from quadkit.contracts.infra.cache.exceptions import (
    CacheError,
    CacheWriteError,
)
from quadkit.logging import get_logger
from quadkit.result import Err, Ok, Result

logger = get_logger(__name__)


class MemoryCacheBackend(CacheBackendProtocol):
    """
    Memory cache backend using quadkit-components MemoryStateStore.

    This backend provides in-memory caching with TTL support by wrapping
    the standardized MemoryStateStore from quadkit-components.
    """

    def __init__(
        self,
        config: CacheOperationConfig | None = None,
        max_size: int | None = None,
        hooks: HookRegistryProtocol | None = None,
    ) -> None:
        """Initialize the memory cache backend.

        Args:
            config: Cache configuration. If None, uses default configuration.
            max_size: Maximum number of cache entries.  When the store is full
                the least-recently-used entry is evicted.  ``None`` disables
                eviction (use only for tests / development).
            hooks: Optional hook registry for lifecycle emission.
        """
        self.config = config or default_cache_config()
        self.max_size = max_size
        self._store = MemoryStateStore(max_size=max_size)
        self._metrics = CacheMetrics()
        self._evictions = 0
        self._hooks = hooks

    async def _emit_action(self, hook_name: str, payload: object) -> None:
        """Emit a cache action hook when a registry is available."""
        if self._hooks is None:
            return

        await self._hooks.call_action(hook_name, payload=payload)

    async def get(self, key: str) -> Result[Any | None, CacheError]:
        """
        Get a value from the cache.

        Args:
            key: The cache key to retrieve.

        Returns:
            Ok(value) if found, Ok(None) if not found, Err(CacheError) on failure.
        """
        try:
            prefixed_key = self.config.make_key(key)
            value = await self._store.get(prefixed_key)
            if value is None:
                await self._metrics.record_miss()
                await self._emit_action(
                    "cache.miss",
                    CacheMissHook(key=key, backend="memory"),
                )
                return Ok(None)

            await self._metrics.record_hit()
            await self._emit_action(
                "cache.hit",
                CacheHitHook(key=key, backend="memory"),
            )
            return Ok(value)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Memory get failed for key '%s': %s", key, e)
            return Err(CacheWriteError(key, str(e)))

    async def set(
        self, key: str, value: Any, ttl: int | None = None
    ) -> Result[None, CacheError]:
        """
        Set a value in the cache with optional TTL.

        Args:
            key: The cache key to set.
            value: The value to cache.
            ttl: Time to live in seconds. If None, uses default TTL.

        Returns:
            Ok(None) if successful, Err(CacheError) on failure.
        """
        try:
            prefixed_key = self.config.make_key(key)
            effective_ttl = ttl or self.config.default_ttl
            await self._store.set(prefixed_key, value, effective_ttl)
            await self._metrics.record_set()
            return Ok(None)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Memory set failed for key '%s': %s", key, e)
            return Err(CacheWriteError(key, str(e)))

    async def delete(self, key: str) -> Result[bool, CacheError]:
        """
        Delete a value from the cache.

        Args:
            key: The cache key to delete.

        Returns:
            Ok(True) if deleted, Ok(False) if not found, Err(CacheError) on failure.
        """
        try:
            prefixed_key = self.config.make_key(key)
            exists = await self._store.get(prefixed_key) is not None
            if exists:
                await self._store.delete(prefixed_key)
                self._evictions += 1
                await self._metrics.record_delete()
                await self._emit_action(
                    "cache.evicted",
                    CacheEntryEvictedHook(key=key, backend="memory"),
                )
                return Ok(True)
            return Ok(False)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Memory delete failed for key '%s': %s", key, e)
            return Err(CacheWriteError(key, str(e)))

    async def exists(self, key: str) -> Result[bool, CacheError]:
        """
        Check if a key exists in the cache.

        Args:
            key: The cache key to check.

        Returns:
            Ok(True) if exists, Ok(False) otherwise, Err(CacheError) on failure.
        """
        try:
            prefixed_key = self.config.make_key(key)
            value = await self._store.get(prefixed_key)
            return Ok(value is not None)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Memory exists check failed for key '%s': %s", key, e)
            return Err(CacheWriteError(key, str(e)))

    async def clear(self) -> Result[None, CacheError]:
        """Clear all values from the cache.

        Returns:
            Ok(None) if successful, Err(CacheError) on failure.
        """
        try:
            await self._store.clear()
            return Ok(None)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            logger.warning("Memory clear failed: %s", e)
            return Err(CacheWriteError("*", str(e)))

    async def get_many(self, keys: list[str]) -> Result[dict[str, Any], CacheError]:
        """
        Get multiple values from the cache.

        Args:
            keys: List of cache keys to retrieve.

        Returns:
            Ok(dict) mapping found keys to values, Err(CacheError) on failure.
        """
        try:
            prefixed_keys = [self.config.make_key(key) for key in keys]
            result_with_prefixes = await self._store.get_bulk(prefixed_keys)

            # Convert back to original keys
            result = {}
            for prefixed_key, value in result_with_prefixes.items():
                original_key = self.config.strip_prefix(prefixed_key)
                result[original_key] = value

            # Update metrics
            found_count = len(result)
            total_count = len(keys)
            await self._metrics.record_hit(found_count)
            await self._metrics.record_miss(total_count - found_count)

            return Ok(result)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Memory get_many failed: %s", e)
            return Err(CacheWriteError("batch", str(e)))

    async def set_many(
        self, items: dict[str, Any], ttl: int | None = None
    ) -> Result[None, CacheError]:
        """
        Set multiple values in the cache.

        Args:
            items: Dictionary of key-value pairs to cache.
            ttl: Time to live in seconds for all items.

        Returns:
            Ok(None) if all items set successfully, Err(CacheError) on failure.
        """
        try:
            effective_ttl = ttl or self.config.default_ttl
            for key, value in items.items():
                prefixed_key = self.config.make_key(key)
                await self._store.set(prefixed_key, value, effective_ttl)

            await self._metrics.record_set(len(items))
            return Ok(None)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Memory set_many failed: %s", e)
            return Err(CacheWriteError("batch", str(e)))

    async def delete_many(self, keys: list[str]) -> Result[int, CacheError]:
        """
        Delete multiple values from the cache.

        Args:
            keys: List of cache keys to delete.

        Returns:
            Ok(count) of deleted keys, Err(CacheError) on failure.
        """
        try:
            count = 0
            for key in keys:
                prefixed_key = self.config.make_key(key)
                if await self._store.get(prefixed_key) is not None:
                    await self._store.delete(prefixed_key)
                    count += 1
                    self._evictions += 1
                    await self._emit_action(
                        "cache.evicted",
                        CacheEntryEvictedHook(key=key, backend="memory"),
                    )

            await self._metrics.record_delete(count)
            return Ok(count)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Memory delete_many failed: %s", e)
            return Err(CacheWriteError("batch", str(e)))

    async def delete_pattern(self, pattern: str) -> Result[int, CacheError]:
        """Delete all keys matching a glob-style pattern.

        Iterates over the in-memory store's known keys (including the
        configured prefix) and deletes those that match *pattern*.

        Args:
            pattern: Glob pattern, e.g. ``"pet:list:*"``.

        Returns:
            Ok(count) of deleted keys, Err(CacheError) on failure.
        """
        try:
            prefix = self.config.key_prefix or ""
            full_pattern = f"{prefix}:{pattern}" if prefix else pattern
            matching = [
                k
                for k in list(self._store._data.keys())
                if fnmatch.fnmatch(k, full_pattern)
            ]
            count = 0
            for key in matching:
                if await self._store.delete(key):
                    count += 1
                    self._evictions += 1
                    await self._emit_action(
                        "cache.evicted",
                        CacheEntryEvictedHook(
                            key=self.config.strip_prefix(key),
                            backend="memory",
                        ),
                    )
            await self._metrics.record_delete(count)
            return Ok(count)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Memory delete_pattern failed for '%s': %s", pattern, e)
            return Err(CacheWriteError(pattern, str(e)))

    def get_stats(self) -> dict[str, int | float | str] | None:
        """Return backend statistics for the admin dashboard.

        Returns:
            Dict with ``hits``, ``misses``, ``evictions``, and ``entries``
            counts, or None when statistics are unavailable.
        """
        store_stats = getattr(self._store, "get_stats", None)
        store_evictions = 0
        store_entries = len(self._store._data)
        if callable(store_stats):
            reported = store_stats() or {}
            store_evictions = int(reported.get("evictions", 0) or 0)
            store_entries = int(reported.get("entries", store_entries) or 0)
        return {
            "hits": self._metrics.hits,
            "misses": self._metrics.misses,
            # Both the backend's own eviction paths (tag/LRU maintenance) and
            # the store's capacity evictions.
            "evictions": self._evictions + store_evictions,
            "entries": store_entries,
        }

    def reset_stats(self) -> None:
        """Reset counters without evicting cached entries."""
        self._metrics.reset()
        self._evictions = 0
        store = self._store
        if hasattr(store, "eviction_count"):
            store.eviction_count = 0

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """
        Perform a health check on the cache backend.

        Returns:
            Structured health check result.
        """
        try:
            store_health = await self._store.health_check()
            return HealthCheckResult(
                component="cache:memory",
                status=HealthStatus.HEALTHY,
                details={
                    "backend": "memory",
                    "store_health": store_health,
                    "metrics": await self._metrics.to_dict(),
                    "config": {
                        "default_ttl": self.config.default_ttl,
                        "key_prefix": self.config.key_prefix,
                    },
                },
            )
        except RuntimeError as e:
            logger.exception("Memory health check failed")
            return HealthCheckResult(
                component="cache:memory",
                status=HealthStatus.UNHEALTHY,
                error=str(e),
                details={
                    "backend": "memory",
                    "metrics": await self._metrics.to_dict(),
                },
            )
