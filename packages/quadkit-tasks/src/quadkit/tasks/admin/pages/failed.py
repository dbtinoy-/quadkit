"""Management page for /admin/tasks/failed."""

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


class TasksFailedPage:
    """Management view for /admin/tasks/failed."""

    def __init__(self, result_store: ResultStore | None = None) -> None:
        self._result_store = result_store

    async def handle(self, request: Any) -> PageContent:
        """Handle request and render failed tasks page."""
        if self._result_store is None:
            return PageContent(
                title="Failed Tasks",
                body=EmptyContent(
                    title="Result Store Unavailable",
                    message="No result store service is configured.",
                    icon="x-circle",
                ),
            )

        try:
            fetch_failed = getattr(self._result_store, "get_failed", None)
            tasks = await fetch_failed() if fetch_failed is not None else []
        except Exception as exc:
            logger.warning("tasks_failed.store_unavailable", error=str(exc))
            return PageContent(
                title="Failed Tasks",
                body=EmptyContent(
                    title="Result Store Error",
                    message="Failed to retrieve failed tasks from the result store.",
                    icon="alert-triangle",
                ),
            )

        if not tasks:
            return PageContent(
                title="Failed Tasks",
                body=EmptyContent(
                    title="No Failed Tasks",
                    message="There are no failed tasks to display.",
                    icon="x-circle",
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
                TableCell(str(getattr(t, "failed_at", ""))),
                TableCell("Failed"),
                TableCell(str(getattr(t, "error", ""))),
            )
            for t in page_tasks
        )

        return PageContent(
            title="Failed Tasks",
            body=TableContent(
                columns=("ID", "Name", "Failed At", "Status", "Error"),
                rows=rows,
            ),
            pagination=PaginationContent(
                page=page,
                total=total,
                per_page=per_page,
                base_url=str(request.url).split("?")[0],
            ),
        )
