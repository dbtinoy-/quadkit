"""
Tiered caching strategy for Quadkit Cache.

Provides a multi-level caching system (L1 memory → L2 distributed)
to optimize for both speed and consistency.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Generic, TypeVar, cast

from quadkit.cache.service.core import CacheService
from quadkit.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class TieredCache(Generic[T]):
    """
    Tiered caching matching (L1 -> L2).

    Checks L1 (typically memory) first, then falls back to L2 (typically Redis).
    Automatically backfills L1 on L2 hits.
    """

    def __init__(
        self,
        cache_service: CacheService,
        l1_backend: str = "memory",
        l2_backend: str = "redis",
        l1_ttl_multiplier: float = 0.5,  # L1 usually has shorter TTL
    ):
        """
        Initialize tiered cache.

        Args:
            cache_service: Cache service instance
            l1_backend: Name of the L1 backend (fast, local)
            l2_backend: Name of the L2 backend (distributed)
            l1_ttl_multiplier: Proportion of the L2 TTL to use for L1
        """
        self.cache_service = cache_service
        self.l1_backend = l1_backend
        self.l2_backend = l2_backend
        self.l1_ttl_multiplier = l1_ttl_multiplier

    async def get(self, key: str, default: Any = None) -> T | None:
        """
        Get value from tiered cache.

        1. Check L1.
        2. If L1 miss, check L2.
        3. If L2 hit, backfill L1 and return.
        """
        # 1. Try L1
        value = await self.cache_service.get(key, backend=self.l1_backend)
        if value is not None:
            logger.debug("TieredCache: L1 hit for key '%s'", key)
            return cast("T | None", value)

        # 2. Try L2
        value = await self.cache_service.get(key, backend=self.l2_backend)
        if value is not None:
            logger.debug("TieredCache: L2 hit for key '%s'", key)

            # 3. Backfill L1
            # Note: We don't know the exact remaining TTL, so we use a heuristic
            # or the service default if we set it.
            # In a more advanced version, we'd store the expiration time in the value.
            await self.cache_service.set(key, value, backend=self.l1_backend)
            return cast("T | None", value)

        return cast("T | None", default)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set value in both L1 and L2."""
        l1_ttl = int(ttl * self.l1_ttl_multiplier) if ttl else None

        # Set in both
        await self.cache_service.set(
            key,
            value,
            ttl=l1_ttl,
            backend=self.l1_backend,
        )
        return await self.cache_service.set(
            key,
            value,
            ttl=ttl,
            backend=self.l2_backend,
        )

    async def delete(self, key: str) -> bool:
        """Delete from both tiers."""
        await self.cache_service.delete(key, backend=self.l1_backend)
        return await self.cache_service.delete(key, backend=self.l2_backend)

    async def shutdown(self) -> None:
        """Shut down the tiered cache in L1 → L2 order.

        Tiers are shut down from innermost (fastest, closest to the app) to
        outermost so that any data still live in L1 at shutdown time has
        already been propagated to L2 during normal ``set()`` calls.
        This order avoids data loss when L1 is an in-process memory backend
        whose contents would be lost on process exit.
        """
        logger.debug("TieredCache.shutdown(): closing L1 backend '%s'", self.l1_backend)
        try:
            l1 = self.cache_service.get_backend(self.l1_backend)  # type: ignore[attr-defined]
            if hasattr(l1, "close"):
                await l1.close()
        except Exception:  # noqa: BLE001 — every tier must be closed, even if one fails
            logger.warning("TieredCache.shutdown(): L1 close failed", exc_info=True)

        logger.debug("TieredCache.shutdown(): closing L2 backend '%s'", self.l2_backend)
        try:
            l2 = self.cache_service.get_backend(self.l2_backend)  # type: ignore[attr-defined]
            if hasattr(l2, "close"):
                await l2.close()
        except Exception:  # noqa: BLE001 — every tier must be closed, even if one fails
            logger.warning("TieredCache.shutdown(): L2 close failed", exc_info=True)

    async def get_or_set(
        self,
        key: str,
        default_func: Callable[[], Any],
        ttl: int | None = None,
    ) -> T:
        """Tiered get-aside pattern."""
        value = await self.get(key)
        if value is not None:
            return value

        # Compute
        result = default_func()
        if hasattr(result, "__await__"):
            value = await result
        else:
            value = result

        # Cache in both
        await self.set(key, value, ttl=ttl)
        return cast("T", value)
