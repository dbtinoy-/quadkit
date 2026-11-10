"""Response caching for LLM operations.

This module provides in-memory and distributed caching for LLM responses
to reduce costs, improve latency, and avoid redundant API calls.

Example:
    >>> from quadkit.contracts import CacheBackendProtocol, LLMClientProtocol, VectorStoreProtocol
    >>>
    >>> cache = LLMCache(ttl=3600)  # 1 hour TTL
    >>> response = await cache.get_or_compute(
    ...     key="what_is_ai",
    ...     compute_fn=lambda: llm.complete("What is AI?")
    ... )

"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
import inspect
from typing import Any, TypeVar, cast

from quadkit.ai.llm.caching.types import CacheEntry, CacheStats
from quadkit.contracts import (
    CacheBackendProtocol,
)
from quadkit.primitives import clock as ambient_clock
from quadkit.security.hashing import ambient as hashing
from quadkit.serialization import dumps

T = TypeVar("T")


class LLMCache:
    """In-memory cache for LLM responses with TTL.

    Implements LRU eviction when max_size is reached.

    Args:
        ttl: Time-to-live in seconds (default: 1 hour).
        max_size: Maximum number of entries (default: 1000).
        max_size_bytes: Maximum cache size in bytes (default: 100MB).

    Example:
        >>> cache = LLMCache(ttl=3600, max_size=500)
        >>> result = await cache.get("key")
        >>> await cache.set("key", "value")

    """

    def __init__(
        self,
        ttl: float = 3600,
        max_size: int = 1000,
        max_size_bytes: int = 100 * 1024 * 1024,
    ):
        """Initialize LLM cache.

        Args:
            ttl: Time-to-live in seconds.
            max_size: Maximum number of entries.
            max_size_bytes: Maximum total size in bytes.

        """
        self.ttl = ttl
        self.max_size = max_size
        self.max_size_bytes = max_size_bytes
        self._cache: dict[str, CacheEntry] = {}
        self._stats = CacheStats()
        self._lock = asyncio.Lock()

    def _hash_key(self, key: str | dict[str, Any]) -> str:
        """Generate cache key hash.

        Args:
            key: String key or dict to hash.

        Returns:
            SHA256 hash of key.

        """
        if isinstance(key, dict):
            # Sort dict for consistent hashing
            key_str = dumps(key, sort_keys=True).decode("utf-8")
        else:
            key_str = str(key)

        return hashing.hash_hex(key_str)

    def _estimate_size(self, value: Any) -> int:
        """Estimate size of value in bytes.

        Args:
            value: Value to estimate.

        Returns:
            Approximate size in bytes.

        """
        try:
            # Convert to JSON for size estimation
            return len(dumps(value))
        except (TypeError, ValueError):
            # Fallback for non-JSON-serializable objects
            return len(str(value).encode("utf-8"))

    def _is_expired(self, entry: CacheEntry) -> bool:
        """Check if cache entry is expired.

        Args:
            entry: Cache entry to check.

        Returns:
            True if expired.

        """
        return ambient_clock.timestamp() > entry.expires_at

    async def _evict_expired(self) -> None:
        """Evict expired entries."""
        expired_keys = [
            key for key, entry in self._cache.items() if self._is_expired(entry)
        ]

        for key in expired_keys:
            entry = self._cache.pop(key)
            self._stats.total_size_bytes -= entry.size_bytes
            self._stats.evictions += 1

        self._stats.total_entries = len(self._cache)

    async def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return

        # Find the least recently accessed entry
        lru_key = min(
            self._cache.keys(),
            key=lambda k: (
                self._cache[k].last_access_at,
                self._cache[k].created_at,
            ),
        )

        entry = self._cache.pop(lru_key)
        self._stats.total_size_bytes -= entry.size_bytes
        self._stats.evictions += 1
        self._stats.total_entries = len(self._cache)

    async def get(self, key: str | dict[str, Any]) -> Any | None:
        """Get value from cache.

        Args:
            key: Cache key (string or dict).

        Returns:
            Cached value or None if not found/expired.

        """
        async with self._lock:
            # Clean up expired entries periodically
            if len(self._cache) > 0 and len(self._cache) % 100 == 0:
                await self._evict_expired()

            cache_key = self._hash_key(key)
            entry = self._cache.get(cache_key)

            if entry is None:
                self._stats.misses += 1
                return None

            if self._is_expired(entry):
                self._cache.pop(cache_key)
                self._stats.total_size_bytes -= entry.size_bytes
                self._stats.evictions += 1
                self._stats.total_entries = len(self._cache)
                self._stats.misses += 1
                return None

            # Update hits and LRU timestamp
            entry.hits += 1
            entry.last_access_at = datetime.now(UTC)
            self._stats.hits += 1
            return entry.value

    async def set(
        self,
        key: str | dict[str, Any],
        value: Any,
        ttl: float | None = None,
    ) -> None:
        """Set value in cache.

        Args:
            key: Cache key (string or dict).
            value: Value to cache.
            ttl: Optional TTL override.

        """
        async with self._lock:
            cache_key = self._hash_key(key)
            ttl_seconds = ttl if ttl is not None else self.ttl
            expires_at = ambient_clock.timestamp() + ttl_seconds
            size = self._estimate_size(value)

            # Check if we need to evict
            # Stop evicting once the cache is empty — a value larger than
            # max_size_bytes (or max_size=0) must still be storable instead
            # of spinning forever on an empty cache.
            while self._cache and (
                len(self._cache) >= self.max_size
                or self._stats.total_size_bytes + size > self.max_size_bytes
            ):
                await self._evict_lru()

            # Remove old entry if exists
            if cache_key in self._cache:
                old_entry = self._cache[cache_key]
                self._stats.total_size_bytes -= old_entry.size_bytes

            # Create new entry
            entry = CacheEntry(
                key=cache_key,
                value=value,
                expires_at=expires_at,
                size_bytes=size,
            )

            self._cache[cache_key] = entry
            self._stats.total_size_bytes += size
            self._stats.total_entries = len(self._cache)

    async def get_or_compute(
        self,
        key: str | dict[str, Any],
        compute_fn: Callable[[], Any],
        ttl: float | None = None,
    ) -> Any:
        """Get from cache or compute and cache result.

        Args:
            key: Cache key.
            compute_fn: Function to compute value if cache miss.
            ttl: Optional TTL override.

        Returns:
            Cached or computed value.

        Example:
            >>> result = await cache.get_or_compute(
            ...     key="greeting",
            ...     compute_fn=lambda: llm.complete("Say hello")
            ... )

        """
        # Try cache first
        cached = await self.get(key)
        if cached is not None:
            return cached

        # Compute value (handle both sync and async functions)
        result = compute_fn()
        if inspect.isawaitable(result):
            value = await result
        else:
            value = result

        # Cache result
        await self.set(key, value, ttl=ttl)
        return value

    async def delete(self, key: str | dict[str, Any]) -> bool:
        """Delete entry from cache.

        Args:
            key: Cache key to delete.

        Returns:
            True if entry was deleted.

        """
        async with self._lock:
            cache_key = self._hash_key(key)
            if cache_key in self._cache:
                entry = self._cache.pop(cache_key)
                self._stats.total_size_bytes -= entry.size_bytes
                self._stats.total_entries = len(self._cache)
                return True
            return False

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self._stats = CacheStats()

    def get_stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            CacheStats object.

        """
        return cast("CacheStats", self._stats.model_copy())


class RedisLLMCache:
    """Redis-backed cache for distributed deployments.

    Requires redis package to be installed.

    Args:
        redis_url: Redis connection URL.
        ttl: Time-to-live in seconds.
        key_prefix: Prefix for all cache keys.

    Example:
        >>> cache = RedisLLMCache(redis_url="redis://localhost:6379")
        >>> await cache.connect()
        >>> result = await cache.get("key")

    """

    def __init__(
        self,
        cache_backend: CacheBackendProtocol,
        ttl: float = 3600,
        key_prefix: str = "llm_cache:",
    ):
        """Initialize Redis cache.

        Args:
            cache_backend: The platform's cache backend.
            ttl: Time-to-live in seconds.
            key_prefix: Prefix for cache keys.

        """
        self._backend = cache_backend
        self.ttl = ttl
        self.key_prefix = key_prefix
        self._stats = CacheStats()

    async def connect(self) -> None:
        """Compatibility method for lifecycle-managed cache."""

    async def disconnect(self) -> None:
        """Compatibility method for lifecycle-managed cache."""

    def _make_key(self, key: str | dict[str, Any]) -> str:
        """Create Redis key with prefix.

        Args:
            key: Cache key.

        Returns:
            Prefixed Redis key.

        """
        if isinstance(key, dict):
            key_str = dumps(key, sort_keys=True).decode("utf-8")
        else:
            key_str = str(key)

        key_hash = hashing.hash_hex(key_str)
        return f"{self.key_prefix}{key_hash}"

    async def get(self, key: str | dict[str, Any]) -> Any | None:
        """Get value from Redis cache.

        Args:
            key: Cache key.

        Returns:
            Cached value or None.

        """
        redis_key = self._make_key(key)
        result = await self._backend.get(redis_key)
        if result.is_err():
            self._stats.misses += 1
            return None
        value = result.unwrap()

        if value is None:
            self._stats.misses += 1
            return None

        self._stats.hits += 1
        return value  # CacheBackendProtocol already handles deserialization

    async def set(
        self,
        key: str | dict[str, Any],
        value: Any,
        ttl: float | None = None,
    ) -> None:
        """Set value in Redis cache.

        Args:
            key: Cache key.
            value: Value to cache.
            ttl: Optional TTL override.

        """
        redis_key = self._make_key(key)
        ttl_seconds = int(ttl if ttl is not None else self.ttl)

        await self._backend.set(
            redis_key,
            value,
            ttl=ttl_seconds,
        )

    async def get_or_compute(
        self,
        key: str | dict[str, Any],
        compute_fn: Callable[[], Any],
        ttl: float | None = None,
    ) -> Any:
        """Get from cache or compute and cache result.

        Args:
            key: Cache key.
            compute_fn: Function to compute value if cache miss.
            ttl: Optional TTL override.

        Returns:
            Cached or computed value.

        """
        cached = await self.get(key)
        if cached is not None:
            return cached

        result = compute_fn()
        if inspect.isawaitable(result):
            value = await result
        else:
            value = result

        await self.set(key, value, ttl=ttl)
        return value

    async def delete(self, key: str | dict[str, Any]) -> bool:
        """Delete entry from cache.

        Args:
            key: Cache key.

        Returns:
            True if deleted.

        """
        redis_key = self._make_key(key)
        result = await self._backend.delete(redis_key)
        # Ok(False) means "nothing deleted" — is_ok() alone would report
        # True for a missing key, contradicting LLMCache.delete semantics.
        return result.unwrap() if result.is_ok() else False

    async def clear(self) -> None:
        """Clear all cache entries (Warning: clears entire backend if not namespaced)."""
        await self._backend.clear()

    def get_stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            CacheStats object.

        """
        return cast("CacheStats", self._stats.model_copy())


class NoOpLLMCache:
    """Pass-through LLM cache used before a real backend is bound.

    The DI container freezes between the register and boot phases, so a
    provider that enables caching at register time but only resolves the
    platform ``CacheBackendProtocol`` at boot time registers this pass-
    through initially; ``LLMCacheWrapper.bind_cache`` swaps in the real
    cache at boot, keeping all container bindings valid.  While active,
    lookups always miss and writes are discarded.
    """

    async def get(self, key: str | dict[str, Any]) -> Any | None:
        """Always miss — no entries are stored."""
        return None

    async def set(
        self,
        key: str | dict[str, Any],
        value: Any,
        ttl: float | None = None,
    ) -> None:
        """Discard — nothing is stored."""
        return

    async def delete(self, key: str | dict[str, Any]) -> bool:
        """Never present — nothing was stored."""
        return False

    async def clear(self) -> None:
        """No-op — there is nothing to clear."""
        return

    def get_stats(self) -> dict[str, Any]:
        """Return empty statistics (the protocol declares a plain mapping)."""
        return {}
