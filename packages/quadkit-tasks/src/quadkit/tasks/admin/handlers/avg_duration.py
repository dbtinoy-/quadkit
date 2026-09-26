"""Average task duration widget handler."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import Stat, StatContent, Tone, WidgetParams
from quadkit.contracts.admin.errors import AdminError
from quadkit.result import Ok, Result


class AvgDurationWidgetHandler:
    """Fetches average task execution duration statistics.

    Args:
        pool_provider: Injected worker pool exposing ``get_pool_stats`` (Any).
    """

    def __init__(self, pool_provider: Any = None) -> None:
        self._pool_provider = pool_provider

    async def get_data(self, params: WidgetParams) -> Result[StatContent, AdminError]:
        """Fetch average duration statistics.

        Mirrors the widget template's two dl rows, including the P95 row's
        static warning class. The template has no tone/threshold logic.

        Args:
            params: Widget parameters.

        Returns:
            Result containing StatContent or AdminError.
        """
        avg_ms = 0.0
        get_pool_stats = getattr(self._pool_provider, "get_pool_stats", None)
        if callable(get_pool_stats):
            pool_stats = get_pool_stats()
            avg_seconds = float(pool_stats.get("average_processing_time", 0.0))
            avg_ms = round(avg_seconds * 1000, 1)
        # P95 has no data source anywhere in quadkit-tasks (WorkerJobStats only
        # tracks a running average, no percentile distribution) — left at 0.0,
        # same documented-placeholder treatment as the activity/health branches.
        p95_ms = 0.0
        return Ok(
            StatContent(
                stats=(
                    Stat(label="Avg", value=f"{avg_ms}ms"),
                    Stat(label="P95", value=f"{p95_ms}ms", tone=Tone.WARNING),
                )
            )
        )


__all__ = ["AvgDurationWidgetHandler"]
