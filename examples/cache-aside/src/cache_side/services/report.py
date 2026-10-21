"""Convention followed: **Service layer** — domain logic lives in a service
the controller adapts; the controller stays a thin HTTP shell.

The cache-aside read path: ``get_report`` asks the stampede-protected cache
for the report key. On a hit the stored payload is returned untouched; on a
miss ``compute`` runs once, its result is stored for ``report_ttl`` seconds,
and every later caller is served from the cache until the entry expires or
``invalidate`` clears it.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cache_side.config import CacheSideConfig
    from quadkit.cache.service.stampede import StampedeProtectedCache
    from quadkit.contracts.infra.cache import CacheBackendProtocol

_CACHE_KEY = "cache_side:report"


class ReportService:
    """Compute a small report once and serve it from the cache thereafter."""

    def __init__(
        self,
        *,
        cache: CacheBackendProtocol,
        protection: StampedeProtectedCache,
        config: CacheSideConfig,
    ) -> None:
        self._cache = cache
        self._protection = protection
        self._config = config
        self._computes = 0

    async def get_report(self) -> dict[str, Any]:
        """Return the report, computing and caching it on a miss."""
        computed = False

        async def compute() -> dict[str, Any]:
            nonlocal computed
            computed = True
            self._computes += 1
            return {
                "total": 42,
                "computed_at": time.time(),
                "computes": self._computes,
            }

        payload = await self._protection.get_or_compute(
            _CACHE_KEY,
            compute,
            ttl=self._config.report_ttl,
        )
        return {**payload, "cached": not computed}

    async def invalidate(self) -> None:
        """Drop the cached report so the next read recomputes."""
        await self._cache.clear()


__all__ = ["ReportService"]
