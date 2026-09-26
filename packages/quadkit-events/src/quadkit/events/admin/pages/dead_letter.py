from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent, PaginationContent
from quadkit.contracts.admin.widget_content import (
    EmptyContent,
    TableCell,
    TableContent,
)
from quadkit.contracts.events import EventBusProtocol
from quadkit.logging import get_logger

logger = get_logger(__name__)


class EventsDeadLetterPage:
    """Dead-letter queue viewer for /admin/events/dead-letter."""

    def __init__(self, event_bus: EventBusProtocol | None = None) -> None:
        self._event_bus = event_bus

    async def handle(self, request: Any) -> PageContent:
        if self._event_bus is None:
            return PageContent(
                title="Dead-Letter Queue",
                body=EmptyContent(
                    title="Event Bus Unavailable",
                    message="No event bus is configured. Dead-letter queue cannot be displayed.",
                    icon="alert-triangle",
                ),
            )

        entries: list[Any] = []
        try:
            store = getattr(self._event_bus, "dead_letter_store", None)
            if store is not None:
                entries = await store.list_entries(limit=100)
        except Exception as exc:
            logger.warning("events_dead_letter.store_unavailable", error=str(exc))
            return PageContent(
                title="Dead-Letter Queue",
                body=EmptyContent(
                    title="Dead-Letter Store Error",
                    message="Failed to retrieve entries from the dead-letter store.",
                    icon="alert-triangle",
                ),
            )

        if not entries:
            return PageContent(
                title="Dead-Letter Queue",
                body=EmptyContent(
                    title="No Dead-Letter Entries",
                    message="No events have been sent to the dead-letter queue.",
                    icon="inbox",
                ),
            )

        rows = tuple(
            (
                TableCell(str(getattr(e, "event_type", ""))),
                TableCell(str(getattr(e, "handler_name", ""))),
                TableCell(str(getattr(e, "failed_at", ""))),
                TableCell("Replayed" if getattr(e, "replayed", False) else "Pending"),
            )
            for e in entries
        )

        return PageContent(
            title="Dead-Letter Queue",
            body=TableContent(
                columns=("Event Type", "Handler", "Failed At", "Status"),
                rows=rows,
            ),
            pagination=PaginationContent(
                page=1,
                total=len(entries),
                per_page=100,
                base_url=str(request.url).split("?")[0],
            ),
        )
