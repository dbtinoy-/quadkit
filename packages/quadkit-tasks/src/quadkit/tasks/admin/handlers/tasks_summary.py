"""Tasks summary widget handler."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import Stat, StatContent, Tone, WidgetParams
from quadkit.contracts.admin.errors import AdminError
from quadkit.result import Ok, Result


class TasksSummaryWidgetHandler:
    """Fetches task queue summary statistics.

    Args:
        queue_provider: Injected task queue (Any until we have a dedicated protocol).
        pool_provider: Injected worker pool exposing ``get_pool_stats`` (Any).
    """

    def __init__(self, queue_provider: Any = None, pool_provider: Any = None) -> None:
        self._queue_provider = queue_provider
        self._pool_provider = pool_provider

    async def get_data(self, params: WidgetParams) -> Result[StatContent, AdminError]:
        """Fetch task summary statistics.

        Mirrors the widget template's four static cells, including each
        cell's static tone class (running is informational, completed is
        success, failed is destructive). The template has no tone/threshold
        logic.

        Args:
            params: Widget parameters.

        Returns:
            Result containing StatContent or AdminError.
        """
        pending = 0
        if self._queue_provider is not None:
            pending = await self._queue_provider.get_task_count()

        running = completed = failed = 0
        get_pool_stats = getattr(self._pool_provider, "get_pool_stats", None)
        if callable(get_pool_stats):
            pool_stats = get_pool_stats()
            running = pool_stats.get("active_workers", 0)
            completed = pool_stats.get("total_jobs_succeeded", 0)
            failed = pool_stats.get("total_jobs_failed", 0)

        return Ok(
            StatContent(
                stats=(
                    Stat(label="Pending", value=str(pending)),
                    Stat(label="Running", value=str(running), tone=Tone.INFO),
                    Stat(label="Completed", value=str(completed), tone=Tone.SUCCESS),
                    Stat(label="Failed", value=str(failed), tone=Tone.DANGER),
                )
            )
        )


__all__ = ["TasksSummaryWidgetHandler"]
