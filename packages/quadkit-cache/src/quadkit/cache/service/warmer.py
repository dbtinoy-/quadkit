"""CacheWarmer — proactive cache pre-loading at boot or on schedule (D6.4).

Complements :class:`~quadkit.cache.service.stampede.StampedeProtectedCache`
(reactive cache fills) with proactive preloading so that the first real
request to a key never incurs a cache miss.

Wire to ``CacheProvider.boot()`` for startup warming or to ``quadkit-tasks``
for scheduled re-warming.

Usage::

    from quadkit.cache.service.warmer import CacheWarmer

    warmer = CacheWarmer(cache=cache_backend, concurrency=10)

    await warmer.warm(
        keys=["home:feed", "config:feature_flags"],
        loader=async def(key): return await db.fetch(key),
        ttl=300,
    )
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol

logger = get_logger(__name__)


class CacheWarmer:
    """Proactively fills cache entries from a loader function.

    Runs all loads concurrently (up to *concurrency* at a time) so large
    warm-up lists complete quickly.

    Args:
        cache: The :class:`~quadkit.contracts.cache.protocols.CacheBackendProtocol`
            to populate.
        concurrency: Maximum number of concurrent loader calls (default: 10).
    """

    def __init__(self, cache: CacheBackendProtocol, concurrency: int = 10) -> None:
        self._cache = cache
        self._concurrency = concurrency

    async def warm(
        self,
        keys: list[str],
        loader: Callable[[str], Awaitable[Any]],
        ttl: int | None = None,
        skip_existing: bool = True,
    ) -> dict[str, bool]:
        """Pre-fill *keys* using *loader*.

        Args:
            keys: Cache keys to warm.
            loader: Async callable that accepts a key and returns the value
                to cache.
            ttl: TTL in seconds for the cached values.
            skip_existing: When ``True`` (default), skip keys that already
                have a cached value to avoid redundant loader calls.

        Returns:
            Dict mapping each key to ``True`` (warmed / already present) or
            ``False`` (loader raised an exception).
        """
        semaphore = asyncio.Semaphore(self._concurrency)
        results: dict[str, bool] = {}

        async def _warm_one(key: str) -> None:
            async with semaphore:
                try:
                    if skip_existing:
                        existing = await self._cache.get(key)
                        if existing is not None:
                            results[key] = True
                            logger.debug("cache_warm_skip", key=key)
                            return

                    value = await loader(key)
                    await self._cache.set(key, value, ttl=ttl)
                    results[key] = True
                    logger.debug("cache_warm_ok", key=key)
                except Exception as e:  # noqa: BLE001 — per-key failure must not abort the entire warm loop
                    results[key] = False
                    logger.warning("cache_warm_failed", key=key, error=str(e))

        await asyncio.gather(*(_warm_one(k) for k in keys))
        warmed = sum(1 for v in results.values() if v)
        logger.info("cache_warm_complete", total=len(keys), warmed=warmed)
        return results

    async def warm_dict(
        self,
        data: dict[str, Any],
        ttl: int | None = None,
    ) -> int:
        """Directly populate the cache from a pre-fetched dictionary.

        Use when the caller has already loaded all values and just needs to
        fill the cache (e.g. after a bulk database query).

        Args:
            data: Mapping of cache key → value.
            ttl: TTL in seconds for the cached values.

        Returns:
            Number of keys successfully written.
        """
        written = 0
        for key, value in data.items():
            try:
                await self._cache.set(key, value, ttl=ttl)
                written += 1
            except Exception as e:  # noqa: BLE001 — per-key failure must not abort the bulk warm
                logger.warning("cache_warm_dict_failed", key=key, error=str(e))
        logger.info("cache_warm_dict_complete", written=written, total=len(data))
        return written


__all__ = ["CacheWarmer"]
