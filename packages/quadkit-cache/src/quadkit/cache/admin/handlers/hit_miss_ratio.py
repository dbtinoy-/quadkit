"""Hit/miss ratio widget handler."""

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


class HitMissRatioWidgetHandler:
    """Fetches cache hit/miss ratio.

    Args:
        cache: Injected CacheBackendProtocol.
    """

    def __init__(self, cache: CacheBackendProtocol) -> None:
        self._cache = cache

    async def get_data(self, params: WidgetParams) -> Result[StatContent, AdminError]:
        """Fetch cache hit/miss stats.

        Degrades to "Unavailable" when the backend lacks the stats capability.

        Args:
            params: Widget parameters.

        Returns:
            Result containing StatContent with hit-rate metrics.
        """
        if not isinstance(self._cache, CacheStatsProtocol):
            return Ok(StatContent(stats=(Stat(label="Hit Rate", value="Unavailable"),)))
        stats = self._cache.get_stats() or {}
        hits = float(stats.get("hits", 0))
        misses = float(stats.get("misses", 0))
        total = hits + misses
        ratio = round(hits / total * 100, 1) if total > 0 else 100.0
        return Ok(
            StatContent(
                stats=(
                    Stat(
                        label=f"Hit Rate ({params.time_window_minutes}m)",
                        value=f"{ratio}%",
                        tone=Tone.SUCCESS if ratio >= 90 else Tone.WARNING,
                    ),
                    Stat(label="Hits", value=str(int(hits))),
                    Stat(label="Misses", value=str(int(misses))),
                )
            )
        )


__all__ = ["HitMissRatioWidgetHandler"]
