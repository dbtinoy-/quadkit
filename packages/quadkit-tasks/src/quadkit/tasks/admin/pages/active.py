"""Management page for /admin/tasks/active."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import (
    EmptyContent,
    TableCell,
    TableContent,
)
from quadkit.logging import get_logger
from quadkit.tasks import WorkerPool

logger = get_logger(__name__)


class TasksActivePage:
    """Management view for /admin/tasks/active."""

    def __init__(self, worker_pool: WorkerPool | None = None) -> None:
        self._worker_pool = worker_pool

    async def handle(self, request: Any) -> PageContent:
        """Handle request and render active tasks page."""
        if self._worker_pool is None:
            return PageContent(
                title="Active Tasks",
                body=EmptyContent(
                    title="Worker Pool Unavailable",
                    message="No worker pool service is configured.",
                    icon="play-circle",
                ),
            )

        try:
            tasks = [
                w.current_job
                for w in self._worker_pool.workers
                if w.current_job is not None
            ]
        except Exception as exc:
            logger.warning("tasks_active.pool_unavailable", error=str(exc))
            return PageContent(
                title="Active Tasks",
                body=EmptyContent(
                    title="Worker Pool Error",
                    message="Failed to retrieve active tasks from the worker pool.",
                    icon="alert-triangle",
                ),
            )

        if not tasks:
            return PageContent(
                title="Active Tasks",
                body=EmptyContent(
                    title="No Active Tasks",
                    message="There are currently no tasks running.",
                    icon="play-circle",
                ),
            )

        rows = tuple(
            (
                TableCell(str(t.id)),
                TableCell(str(t.name)),
                TableCell(str(getattr(t, "started_at", ""))),
                TableCell(str(getattr(t, "duration_ms", ""))),
            )
            for t in tasks
        )

        return PageContent(
            title="Active Tasks",
            body=TableContent(columns=("ID", "Name", "Started", "Duration"), rows=rows),
        )
