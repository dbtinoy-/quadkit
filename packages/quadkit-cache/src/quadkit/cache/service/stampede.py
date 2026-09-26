"""
Stampede protection utilities extracted from `protection.py`.

Contains `CacheEntry` dataclass and `StampedeProtectedCache` generic class.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import timedelta
import inspect
import random
from typing import Any
import weakref

from quadkit.cache.types import CacheEntry
from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol
from quadkit.di.decorators import inject
from quadkit.logging import get_logger
from quadkit.serialization import dumps, loads

logger = get_logger(__name__)


@inject
class StampedeProtectedCache:
    """Cache with stampede (thundering-herd) protection.

    Implements the single-flight pattern.  All concurrent requests for the
    same key coalesce into a single compute call while the first request is
    in-flight.

    The backing store is injected as a :class:`~quadkit.contracts.cache.protocols.CacheBackendProtocol`
    so the class remains decoupled from any specific cache implementation
    (Redis, Memcached, in-memory, etc.).
    """

    def __init__(
        self,
        cache: CacheBackendProtocol,
        *,
        lock_timeout: int = 10,
        lock_wait_timeout: float = 30,
    ) -> None:
        self.cache = cache
        self.lock_timeout = lock_timeout
        self.lock_wait_timeout = lock_wait_timeout
        self._locks: weakref.WeakValueDictionary[str, asyncio.Lock] = (
            weakref.WeakValueDictionary()
        )
        self._pending: dict[str, asyncio.Task] = {}

    async def get_or_compute(
        self,
        key: str,
        compute: Callable[..., Any],
        ttl: int = 300,
        *args: Any,
        ttl_jitter: float = 0.0,
        **kwargs: Any,
    ) -> Any:
        """Get value from cache or compute it with stampede protection.

        Uses single-flight pattern to prevent cache stampede.

        Args:
            key: Cache key
            compute: Function to compute value if not cached
            ttl: Cache TTL in seconds
            *args: Arguments for compute function
            ttl_jitter: Fractional TTL jitter (e.g. 0.2 = ±20%).  When
                non-zero the actual TTL stored in Redis is randomised within
                ``ttl * (1 ± ttl_jitter)`` to spread expiry times and
                reduce thundering-herd effects.
            **kwargs: Keyword arguments for compute function

        Returns:
            Cached or computed value
        """
        # Try to get from cache first
        cached = await self._get_from_cache(key)
        if cached is not None and not cached.is_expired:
            logger.debug("cache_hit", key=key)
            return cached.value

        # Use single-flight pattern.
        # Keep a strong local reference so the lock is not GC'd between
        # creation and acquisition (WeakValueDictionary holds only weak refs).
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock

        async with lock:
            # Double-check after acquiring lock
            cached = await self._get_from_cache(key)
            if cached is not None and not cached.is_expired:
                logger.debug("cache_hit_after_lock", key=key)
                return cached.value

            # Check if another task is already computing
            if key in self._pending:
                logger.debug("waiting_for_pending", key=key)
                try:
                    return await self._pending[key]
                except (RuntimeError, ValueError, OSError, asyncio.CancelledError):
                    # If pending task failed, continue to compute ourselves
                    pass

            # Create task to compute value
            effective_ttl = self._add_jitter(ttl, ttl_jitter)
            task = asyncio.create_task(
                self._compute_and_cache(key, compute, effective_ttl, *args, **kwargs),
            )
            self._pending[key] = task

            try:
                return await task
            finally:
                self._pending.pop(key, None)
                if key in self._locks and not self._locks[key].locked():
                    del self._locks[key]

    async def _get_from_cache(self, key: str) -> CacheEntry | None:
        """Get cache entry via CacheBackendProtocol."""
        from datetime import datetime

        try:
            response = await self.cache.get(f"cache:{key}")
            # Backends return Result[T | None, CacheError]; unwrap so the
            # envelope below always sees the plain stored value.
            if hasattr(response, "is_ok"):
                data = response.unwrap() if response.is_ok() else None
            else:
                data = response
            if not data:
                return None

            parsed = loads(data) if isinstance(data, (str, bytes)) else data
            if not isinstance(parsed, dict) or "value" not in parsed:
                return None
            return CacheEntry(
                value=parsed["value"],
                cached_at=datetime.fromisoformat(parsed["cached_at"]),
                expires_at=datetime.fromisoformat(parsed["expires_at"]),
            )
        except Exception as e:  # noqa: BLE001 — a failed cache read degrades to a miss, never a raw exception
            logger.error("cache_get_failed", key=key, error=str(e))
            return None

    async def _compute_and_cache(
        self,
        key: str,
        compute: Callable[..., Any],
        ttl: int,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Compute value and store in cache."""
        import time

        start_time = time.time()

        try:
            # Call compute function
            if inspect.iscoroutinefunction(compute):
                value = await compute(*args, **kwargs)
            else:
                value = compute(*args, **kwargs)

            compute_time = time.time() - start_time

            # Create cache entry
            from datetime import UTC, datetime

            cached_at = datetime.now(UTC)
            expires_at = cached_at + timedelta(seconds=ttl)

            entry = CacheEntry(
                value=value,
                cached_at=cached_at,
                expires_at=expires_at,
            )

            # Store in cache
            cache_data = {
                "value": entry.value,
                "cached_at": entry.cached_at.isoformat(),
                "expires_at": entry.expires_at.isoformat(),
            }

            await self.cache.set(
                f"cache:{key}",
                dumps(cache_data).decode(),
                ttl=ttl,
            )

            logger.info(
                "cache_set",
                key=key,
                ttl=ttl,
                compute_time_ms=compute_time * 1000,
            )

            return value

        except Exception as e:
            logger.error("compute_failed", key=key, error=str(e))
            raise

    async def invalidate(self, key: str) -> bool:
        """Invalidate a cache entry.

        Args:
            key: Cache key to invalidate

        Returns:
            True if entry was deleted
        """
        try:
            deleted = await self.cache.delete(f"cache:{key}")
            logger.debug("cache_invalidated", key=key, deleted=deleted)
            return deleted  # type: ignore[return-value]
        except Exception as e:  # noqa: BLE001 — a failed cache read degrades to a miss, never a raw exception
            logger.error("cache_invalidate_failed", key=key, error=str(e))
            return False

    def _add_jitter(self, ttl: int, jitter_factor: float) -> int:
        """Return TTL with optional random jitter applied.

        Args:
            ttl: Base TTL in seconds.
            jitter_factor: Fractional spread (e.g. 0.2 = ±20%).  Pass
                0.0 to get the exact ``ttl`` back.

        Returns:
            TTL adjusted by a uniform random offset within the jitter range.
        """
        if jitter_factor == 0.0:
            return ttl
        delta = int(ttl * jitter_factor)
        return ttl + random.randint(-delta, delta)  # noqa: S311 — TTL jitter (non-crypto)

    async def _should_refresh_early(
        self,
        entry: CacheEntry,
        ttl: int,
    ) -> bool:
        """Return True when probabilistic early refresh should be triggered.

        Uses the XFetch algorithm heuristic: the closer a cache entry is
        to expiry (relative to its full TTL) the higher the probability of
        refreshing early, preventing a thundering herd when the entry does
        finally expire.

        Args:
            entry: Current cache entry.
            ttl: Original TTL the entry was stored with (seconds).

        Returns:
            True if the caller should refresh the entry now.
        """
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        time_left = (entry.expires_at - now).total_seconds()

        # Fresh enough — do not refresh
        if time_left > ttl * 0.5:
            return False

        # The closer to expiry the higher the probability
        staleness = 1.0 - (time_left / ttl)
        return random.random() < staleness  # noqa: S311 — probabilistic refresh (non-crypto)
