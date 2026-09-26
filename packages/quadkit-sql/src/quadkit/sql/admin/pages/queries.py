from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent, PaginationContent
from quadkit.contracts.admin.widget_content import (
    EmptyContent,
    TableCell,
    TableContent,
)
from quadkit.contracts.data.sql.query_log import QueryLoggerProtocol
from quadkit.logging import get_logger

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


class SqlQueriesPage:
    def __init__(
        self,
        query_logger: QueryLoggerProtocol | None = None,
    ) -> None:
        self._query_logger = query_logger

    async def handle(self, request: Any) -> PageContent:
        if self._query_logger is None:
            return PageContent(
                title="Recent Queries",
                body=EmptyContent(
                    title="Query Logging Disabled",
                    message="No query logger is configured. Enable query logging to see recent queries.",
                    icon="search",
                ),
            )

        try:
            entries = await self._query_logger.get_recent_queries(limit=10_000)
        except Exception:
            return PageContent(
                title="Recent Queries",
                body=EmptyContent(
                    title="Error",
                    message="Failed to load recent queries. Check the server logs for details.",
                    icon="alert-triangle",
                ),
            )

        if not entries:
            return PageContent(
                title="Recent Queries",
                body=EmptyContent(
                    title="No Queries",
                    message="No queries have been logged yet.",
                    icon="search",
                ),
            )

        page, per_page = _paging(request)
        total = len(entries)
        page = min(page, max(1, (total + per_page - 1) // per_page))
        offset = (page - 1) * per_page
        page_entries = entries[offset : offset + per_page]

        rows = tuple(
            (
                TableCell(m.sql[:80] + "..." if len(m.sql) > 80 else m.sql),
                TableCell(f"{int(m.execution_time * 1000)}ms"),
                TableCell(m.timestamp.isoformat() if m.timestamp else ""),
            )
            for m in page_entries
        )

        return PageContent(
            title="Recent Queries",
            body=TableContent(columns=("Query", "Duration", "Timestamp"), rows=rows),
            pagination=PaginationContent(
                page=page,
                total=total,
                per_page=per_page,
                base_url=str(request.url).split("?")[0],
            ),
        )
