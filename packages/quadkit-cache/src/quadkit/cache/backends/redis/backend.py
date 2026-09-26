"""
Redis cache backend implementation using the centralized StateStoreProtocol protocol.

This module provides a cache backend that wraps the StateStoreProtocol
protocol, ensuring DRY compliance and consistency.
"""

from __future__ import annotations

from typing import Any

from quadkit.cache.config import CacheOperationConfig, default_cache_config
from quadkit.cache.hooks import CacheEntryEvictedHook, CacheHitHook, CacheMissHook
from quadkit.cache.types import CacheMetrics
from quadkit.contracts import CacheBackendProtocol
from quadkit.contracts.core import (
    HealthCheckResult,
    HealthStatus,
    HookRegistryProtocol,
)
from quadkit.contracts.infra import StateStoreProtocol
from quadkit.contracts.infra.cache.exceptions import CacheError, CacheWriteError
from quadkit.logging import get_logger
from quadkit.result import Err, Ok, Result

logger = get_logger(__name__)


class RedisCacheBackend(CacheBackendProtocol):
    """
    Redis cache backend using StateStoreProtocol protocol.

    This backend provides Redis-based distributed caching with TTL support
    by wrapping the standardized StateStoreProtocol protocol.
    """

    def __init__(
        self,
        store: StateStoreProtocol,
        config: CacheOperationConfig | None = None,
        hooks: HookRegistryProtocol | None = None,
    ):
        """
        Initialize the Redis cache backend.

        Args:
            store: StateStoreProtocol implementation for key-value operations.
            config: Cache configuration. If None, uses default configuration.
            hooks: Optional hook registry for lifecycle emission.
        """
        self.config = config or default_cache_config()
        self._store = store
        self._metrics = CacheMetrics()
        self._evictions = 0
        self._hooks = hooks

    def get_underlying_client(self) -> Any | None:
        """Return the underlying Redis client for app.state integration.

        Returns the Redis client from the underlying StateStore, or None if
        not available (e.g., not a Redis backend).
        """
        if hasattr(self._store, "_client"):
            return self._store._client
        return None

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
                    CacheMissHook(key=key, backend="redis"),
                )
                return Ok(None)

            await self._metrics.record_hit()
            await self._emit_action(
                "cache.hit",
                CacheHitHook(key=key, backend="redis"),
            )
            return Ok(value)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Redis get failed for key '%s': %s", key, e)
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
            logger.warning("Redis set failed for key '%s': %s", key, e)
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
                    CacheEntryEvictedHook(key=key, backend="redis"),
                )
                return Ok(True)
            return Ok(False)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Redis delete failed for key '%s': %s", key, e)
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
            logger.warning("Redis exists check failed for key '%s': %s", key, e)
            return Err(CacheWriteError(key, str(e)))

    async def clear(self) -> Result[None, CacheError]:
        """Clear all values from the cache.

        Uses pattern-based deletion to clear only prefixed keys.
        This is safer than FLUSHDB as it only clears cache keys.

        Returns:
            Ok(None) if successful, Err(CacheError) on failure.
        """
        try:
            prefix = self.config.key_prefix or ""
            pattern = f"{prefix}:*" if prefix else "*"

            if hasattr(self._store, "keys"):
                keys = await self._store.keys(pattern)
                if keys:
                    if hasattr(self._store, "pipeline"):
                        pipe = self._store.pipeline()
                        for key in keys:
                            pipe.delete(key)
                        await pipe.execute()
                    else:
                        for key in keys:
                            await self._store.delete(key)
                    for key in keys:
                        await self._emit_action(
                            "cache.evicted",
                            CacheEntryEvictedHook(
                                key=self.config.strip_prefix(key),
                                backend="redis",
                            ),
                        )
            elif hasattr(self._store, "clear"):
                await self._store.clear()
            else:
                logger.warning("Redis store does not support clear operation")
                return Err(CacheWriteError("*", "Store does not support clear"))
            return Ok(None)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Redis clear failed: %s", e)
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
            result_with_prefixes = await self._store.get_bulk(prefixed_keys)  # type: ignore[attr-defined]

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
            logger.warning("Redis get_many failed: %s", e)
            return Err(CacheWriteError("batch", str(e)))

    async def set_many(
        self, items: dict[str, Any], ttl: int | None = None
    ) -> Result[None, CacheError]:
        """
        Set multiple values in the cache using pipeline.

        Args:
            items: Dictionary of key-value pairs to cache.
            ttl: Time to live in seconds for all items.

        Returns:
            Ok(None) if all items set successfully, Err(CacheError) on failure.
        """
        try:
            effective_ttl = ttl or self.config.default_ttl

            # Try to use pipeline if available
            if hasattr(self._store, "pipeline"):
                pipe = self._store.pipeline()
                for key, value in items.items():
                    prefixed_key = self.config.make_key(key)
                    pipe.set(prefixed_key, value, ex=effective_ttl)
                await pipe.execute()
            else:
                # Fallback to sequential
                for key, value in items.items():
                    prefixed_key = self.config.make_key(key)
                    await self._store.set(prefixed_key, value, effective_ttl)

            await self._metrics.record_set(len(items))
            return Ok(None)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Redis set_many failed: %s", e)
            return Err(CacheWriteError("batch", str(e)))

    async def delete_many(self, keys: list[str]) -> Result[int, CacheError]:
        """
        Delete multiple values from the cache using pipeline.

        Args:
            keys: List of cache keys to delete.

        Returns:
            Ok(count) of deleted keys, Err(CacheError) on failure.
        """
        try:
            prefixed_keys = [self.config.make_key(key) for key in keys]
            count = 0

            # Try to use pipeline if available
            if hasattr(self._store, "pipeline"):
                pipe = self._store.pipeline()
                for key in prefixed_keys:
                    pipe.delete(key)
                await pipe.execute()
                count = len(keys)
                for key in keys:
                    await self._emit_action(
                        "cache.evicted",
                        CacheEntryEvictedHook(key=key, backend="redis"),
                    )
            else:
                # Fallback to sequential
                for key in prefixed_keys:
                    await self._store.delete(key)
                count = len(keys)
                for key in keys:
                    await self._emit_action(
                        "cache.evicted",
                        CacheEntryEvictedHook(key=key, backend="redis"),
                    )

            self._evictions += count
            await self._metrics.record_delete(count)
            return Ok(count)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Redis delete_many failed: %s", e)
            return Err(CacheWriteError("batch", str(e)))

    async def delete_pattern(self, pattern: str) -> Result[int, CacheError]:
        """Delete all Redis keys matching a glob-style pattern.

        Uses SCAN (non-blocking) to find matching keys then DEL or pipeline
        to remove them.  The configured key prefix is prepended to *pattern*
        automatically.

        Args:
            pattern: Glob pattern, e.g. ``"pet:list:*"``.

        Returns:
            Ok(count) of deleted keys, Err(CacheError) on failure.
        """
        try:
            prefix = self.config.key_prefix or ""
            full_pattern = f"{prefix}:{pattern}" if prefix else pattern

            if not hasattr(self._store, "keys"):
                logger.warning(
                    "Redis store does not support keys(); skipping pattern delete for '%s'",
                    pattern,
                )
                return Ok(0)

            matching_keys = await self._store.keys(full_pattern)
            if not matching_keys:
                return Ok(0)

            if hasattr(self._store, "pipeline"):
                pipe = self._store.pipeline()
                for key in matching_keys:
                    pipe.delete(key)
                await pipe.execute()
            else:
                for key in matching_keys:
                    await self._store.delete(key)

            for key in matching_keys:
                await self._emit_action(
                    "cache.evicted",
                    CacheEntryEvictedHook(
                        key=self.config.strip_prefix(key),
                        backend="redis",
                    ),
                )

            count = len(matching_keys)
            self._evictions += count
            await self._metrics.record_delete(count)
            return Ok(count)
        except Exception as e:  # noqa: BLE001 — any backend failure becomes Err(CacheError), never a raw exception
            await self._metrics.record_error()
            logger.warning("Redis delete_pattern failed for '%s': %s", pattern, e)
            return Err(CacheWriteError(pattern, str(e)))

    def get_stats(self) -> dict[str, int | float | str] | None:
        """Return backend statistics for the admin dashboard.

        Returns:
            Dict with ``hits``, ``misses``, ``evictions``, and ``entries``
            counts, or None when statistics are unavailable.
        """
        return {
            "hits": self._metrics.hits,
            "misses": self._metrics.misses,
            "evictions": self._evictions,
            "entries": 0,
        }

    def reset_stats(self) -> None:
        """Reset counters without deleting Redis values."""
        self._metrics.reset()
        self._evictions = 0

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """
        Perform a health check on the cache backend.

        Returns:
            Structured health check result.
        """
        try:
            store_health = await self._store.health_check()  # type: ignore[attr-defined]
            is_healthy = store_health.is_healthy()

            return HealthCheckResult(
                component="cache:redis",
                status=HealthStatus.HEALTHY if is_healthy else HealthStatus.UNHEALTHY,
                details={
                    "backend": "redis",
                    "store_health": store_health,
                    "metrics": await self._metrics.to_dict(),
                    "config": {
                        "default_ttl": self.config.default_ttl,
                        "key_prefix": self.config.key_prefix,
                    },
                },
            )
        except Exception as e:
            logger.exception("Redis health check failed")
            return HealthCheckResult(
                component="cache:redis",
                status=HealthStatus.UNHEALTHY,
                error=str(e),
                details={
                    "backend": "redis",
                    "metrics": await self._metrics.to_dict(),
                },
            )
