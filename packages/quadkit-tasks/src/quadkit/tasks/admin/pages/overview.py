"""Management overview page for /admin/tasks."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import Stat, StatContent
from quadkit.logging import get_logger
from quadkit.tasks import TaskScheduler
from quadkit.tasks.execution.metrics import TaskMetricsCollector

logger = get_logger(__name__)


class TasksOverviewPage:
    """Management overview for /admin/tasks."""

    def __init__(
        self,
        scheduler: TaskScheduler | None = None,
        metrics_collector: TaskMetricsCollector | None = None,
    ) -> None:
        self._scheduler = scheduler
        self._metrics_collector = metrics_collector

    async def handle(self, request: Any) -> PageContent:
        """Handle request and render overview page."""
        running = 0
        completed = 0
        failed = 0
        avg_duration_ns = 0
        max_concurrency = "N/A"
        queue_size = "N/A"
        worker_count = "N/A"
        scheduler_status = "N/A"

        try:
            if self._scheduler is not None:
                running = getattr(self._scheduler, "running_count", 0)
                completed = getattr(self._scheduler, "completed_count", 0)
                failed = getattr(self._scheduler, "failed_count", 0)
                max_concurrency = str(
                    getattr(self._scheduler, "max_concurrency", "N/A")
                )
                queue_size = str(getattr(self._scheduler, "queue_size", "N/A"))
                worker_count = str(getattr(self._scheduler, "worker_count", "N/A"))
                scheduler_status = str(getattr(self._scheduler, "status", "N/A"))
        except Exception as exc:
            logger.warning("tasks_overview.scheduler_unavailable", error=str(exc))

        try:
            if self._metrics_collector is not None:
                avg_duration_ns = getattr(
                    self._metrics_collector, "average_duration_ns", 0
                )
        except Exception as exc:
            logger.warning("tasks_overview.metrics_unavailable", error=str(exc))

        avg_ms = int(avg_duration_ns / 1_000_000) if avg_duration_ns else 0

        return PageContent(
            title="Tasks",
            body=StatContent(
                stats=(
                    Stat(label="Running", value=str(running), icon="play-circle"),
                    Stat(label="Completed", value=str(completed), icon="check-circle"),
                    Stat(label="Failed", value=str(failed), icon="x-circle"),
                    Stat(label="Avg Duration", value=f"{avg_ms}ms", icon="clock"),
                    Stat(
                        label="Max Concurrency",
                        value=max_concurrency,
                        icon="activity",
                    ),
                    Stat(label="Queue Size", value=queue_size, icon="list"),
                    Stat(label="Worker Count", value=worker_count, icon="users"),
                    Stat(label="Status", value=scheduler_status, icon="activity"),
                )
            ),
        )
