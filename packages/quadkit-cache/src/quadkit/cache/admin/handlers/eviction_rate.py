"""Eviction rate widget handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.admin import (
    CacheStatsProtocol,
    Stat,
    StatContent,
    Tone,
    WidgetParams,
)
from quadkit.contracts.admin.errors import AdminError
from quadkit.result import Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.infra.cache import CacheBackendProtocol


class EvictionRateWidgetHandler:
    """Fetches cache eviction rate.

    Args:
        cache: Injected CacheBackendProtocol.
    """

    def __init__(self, cache: CacheBackendProtocol) -> None:
        self._cache = cache

    async def get_data(self, params: WidgetParams) -> Result[StatContent, AdminError]:
        """Fetch cache eviction stats.

        Degrades to "Unavailable" when the backend lacks the stats capability.

        Args:
            params: Widget parameters.

        Returns:
            Result containing StatContent with eviction metrics.
        """
        if not isinstance(self._cache, CacheStatsProtocol):
            return Ok(
                StatContent(stats=(Stat(label="Evictions/sec", value="Unavailable"),))
            )
        stats = self._cache.get_stats() or {}
        total_evictions = int(stats.get("evictions", 0))

        # Compute evictions per second over the configured window.
        window_seconds = params.time_window_minutes * 60
        evictions_per_second = (
            total_evictions / window_seconds if window_seconds > 0 else 0.0
        )
        evictions_per_second = round(evictions_per_second, 2)

        # Template has no tone logic (static neutral styling) — mirror statically.
        return Ok(
            StatContent(
                stats=(
                    Stat(
                        label="Evictions/sec",
                        value=f"{evictions_per_second}/s",
                        tone=Tone.DEFAULT,
                    ),
                    Stat(
                        label="Total evictions",
                        value=str(total_evictions),
                        tone=Tone.DEFAULT,
                    ),
                )
            )
        )


__all__ = ["EvictionRateWidgetHandler"]
