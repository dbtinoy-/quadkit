"""Token caching utilities for authentication middleware."""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import threading
from typing import TYPE_CHECKING, Any

from quadkit.primitives import clock as ambient_clock

if TYPE_CHECKING:
    from quadkit.contracts.infra.cache import CacheBackendProtocol


class TokenCache:
    """Cache for JWT tokens with LRU eviction and TTL support.

    Implements:
    - TTL (time-to-live) for entries
    - LRU (least recently used) eviction when max_size is reached
    - Automatic cleanup of expired entries
    - Optional backend cache integration via CacheBackendProtocol protocol

    When no CacheBackendProtocol is provided, this falls back to an in-memory LRU
    cache (L1 layer using :class:`collections.OrderedDict`).  For production
    deployments—especially multi-worker or multi-host setups—inject a
    distributed backend.  The recommended options are:

    * ``quadkit.cache.backends.memory.MemoryCacheBackend`` (from
      *quadkit-cache*) for a process-level shared cache with richer
      configuration.
    * A Redis-backed ``CacheBackendProtocol`` implementation for cross-process token
      invalidation.

    Note: ``quadkit-auth`` does not import from ``quadkit-cache`` directly
    (that would violate the extension-package boundary); pass the backend
    via constructor injection instead.
    """

    def __init__(
        self,
        max_size: int = 10_000,
        ttl_seconds: float = 300.0,
        cache_backend: CacheBackendProtocol | None = None,
    ):
        """Initialize token cache.

        Args:
            max_size: Maximum number of tokens to cache in L1 (local) layer.
            ttl_seconds: Time-to-live for cached entries in seconds.
            cache_backend: Optional L2 cache backend for distributed caching.
        """
        self._lock = threading.Lock()
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._backend = cache_backend
        self._hits = 0
        self._misses = 0

    def _cleanup_expired(self) -> None:
        """Remove expired entries from cache."""
        now = ambient_clock.monotonic()
        expired_keys = [k for k, v in self._cache.items() if v["expires_at"] <= now]
        for k in expired_keys:
            del self._cache[k]

    def _evict_if_needed(self) -> None:
        """Evict oldest entry if cache is full."""
        while len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)

    async def get(self, token: str) -> Any | None:
        """Get cached user for token, or None if not cached/expired.

        Checks L1 (local) first, then L2 (backend) if available.
        """
        now = ambient_clock.monotonic()
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        with self._lock:
            cached = self._cache.get(token_hash)

            if cached is not None and cached["expires_at"] > now:
                self._hits += 1
                self._cache.move_to_end(token_hash)
                return cached["user"]

            if cached is not None:
                del self._cache[token_hash]

        if self._backend is not None:
            cached = None
            get_result = await self._backend.get(f"token:{token_hash}")
            if get_result.is_ok():
                cached = get_result.unwrap()
            if cached is not None:
                self._hits += 1
                await self.set(token, cached)
                return cached

        self._misses += 1
        return None

    async def set(self, token: str, user: Any) -> None:
        """Cache user for token.

        Stores in both L1 (local) and L2 (backend) if available.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        expires_at = ambient_clock.monotonic() + self._ttl

        with self._lock:
            self._cleanup_expired()
            self._evict_if_needed()

            self._cache[token_hash] = {
                "user": user,
                "expires_at": expires_at,
            }
            self._cache.move_to_end(token_hash)

        if self._backend is not None:
            await self._backend.set(f"token:{token_hash}", user, ttl=int(self._ttl))

    async def invalidate(self, token: str) -> None:
        """Invalidate a specific token from cache."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        with self._lock:
            self._cache.pop(token_hash, None)

        if self._backend is not None:
            await self._backend.delete(f"token:{token_hash}")

    def clear(self) -> None:
        """Clear all cached tokens."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

        if self._backend is not None:
            pass

    def stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with hits, misses, size, max_size, and hit_rate.
        """
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total * 100) if total > 0 else 0.0
            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._cache),
                "max_size": self._max_size,
                "hit_rate_percent": round(hit_rate, 2),
            }


__all__ = ["TokenCache"]
