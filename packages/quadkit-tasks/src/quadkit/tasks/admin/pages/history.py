"""Management page for /admin/tasks/history."""

from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent, PaginationContent
from quadkit.contracts.admin.widget_content import (
    EmptyContent,
    TableCell,
    TableContent,
)
from quadkit.logging import get_logger
from quadkit.tasks import ResultStore

logger = get_logger(__name__)

DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 200


def _query_int(request: Any, name: str, default: int, lo: int, hi: int) -> int:
    try:
        value = int(request.query_params.get(name, default))
    except (TypeError, ValueError):
        value = default
    return max(lo, min(value, hi))


def _paging(request: Any) -> tuple[int, int]:
    page = _query_int(request, "page", 1, 1, 10**6)
    per_page = _query_int(request, "per_page", DEFAULT_PER_PAGE, 1, MAX_PER_PAGE)
    return page, per_page


class TasksHistoryPage:
    """Management view for /admin/tasks/history."""

    def __init__(self, result_store: ResultStore | None = None) -> None:
        self._result_store = result_store

    async def handle(self, request: Any) -> PageContent:
        """Handle request and render task history page."""
        if self._result_store is None:
            return PageContent(
                title="Task History",
                body=EmptyContent(
                    title="Result Store Unavailable",
                    message="No result store service is configured.",
                    icon="clock",
                ),
            )

        try:
            fetch_completed = getattr(self._result_store, "get_completed", None)
            tasks = await fetch_completed() if fetch_completed is not None else []
        except Exception as exc:
            logger.warning("tasks_history.store_unavailable", error=str(exc))
            return PageContent(
                title="Task History",
                body=EmptyContent(
                    title="Result Store Error",
                    message="Failed to retrieve completed tasks from the result store.",
                    icon="alert-triangle",
                ),
            )

        if not tasks:
            return PageContent(
                title="Task History",
                body=EmptyContent(
                    title="No Completed Tasks",
                    message="No tasks have been completed yet.",
                    icon="clock",
                ),
            )

        page, per_page = _paging(request)
        total = len(tasks)
        page = min(page, max(1, (total + per_page - 1) // per_page))
        offset = (page - 1) * per_page
        page_tasks = tasks[offset : offset + per_page]

        rows = tuple(
            (
                TableCell(str(t.id)),
                TableCell(str(t.name)),
                TableCell(str(getattr(t, "completed_at", ""))),
                TableCell(str(getattr(t, "duration_ms", ""))),
                TableCell(str(getattr(t, "status", "completed"))),
            )
            for t in page_tasks
        )

        return PageContent(
            title="Task History",
            body=TableContent(
                columns=("ID", "Name", "Completed", "Duration", "Status"),
                rows=rows,
            ),
            pagination=PaginationContent(
                page=page,
                total=total,
                per_page=per_page,
                base_url=str(request.url).split("?")[0],
            ),
        )
