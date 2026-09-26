from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent, PaginationContent
from quadkit.contracts.admin.widget_content import (
    EmptyContent,
    TableCell,
    TableContent,
)
from quadkit.contracts.events import EventStoreProtocol
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


class EventsHistoryPage:
    """Event history for /admin/events/history."""

    def __init__(self, store: EventStoreProtocol | None = None) -> None:
        self._store = store

    async def handle(self, request: Any) -> PageContent:
        if self._store is None:
            return PageContent(
                title="Event History",
                body=EmptyContent(
                    title="Event Store Unavailable",
                    message="No event store is configured. History cannot be displayed.",
                    icon="clock",
                ),
            )

        events: list[Any] = []
        try:
            events = await self._store.read_all(position=0, count=None)
        except Exception as exc:
            logger.warning("events_history.store_unavailable", error=str(exc))
            return PageContent(
                title="Event History",
                body=EmptyContent(
                    title="Event Store Error",
                    message="Failed to retrieve events from the event store.",
                    icon="alert-triangle",
                ),
            )

        if not events:
            return PageContent(
                title="Event History",
                body=EmptyContent(
                    title="No Events",
                    message="No events have been recorded yet.",
                    icon="inbox",
                ),
            )

        ordered = events[::-1]
        page, per_page = _paging(request)
        total = len(ordered)
        page = min(page, max(1, (total + per_page - 1) // per_page))
        offset = (page - 1) * per_page
        page_events = ordered[offset : offset + per_page]

        rows = tuple(
            (
                TableCell(str(getattr(e, "event_id", ""))),
                TableCell(type(e).__name__),
                TableCell(str(getattr(e, "occurred_at", ""))),
            )
            for e in page_events
        )

        return PageContent(
            title="Event History",
            body=TableContent(columns=("ID", "Type", "Occurred At"), rows=rows),
            pagination=PaginationContent(
                page=page,
                total=total,
                per_page=per_page,
                base_url=str(request.url).split("?")[0],
            ),
        )
