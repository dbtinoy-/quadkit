from __future__ import annotations

from typing import Any

from quadkit.contracts.admin import PageContent
from quadkit.contracts.admin.widget_content import Stat, StatContent
from quadkit.contracts.events import EventBusProtocol
from quadkit.logging import get_logger

logger = get_logger(__name__)


class EventsOverviewPage:
    """Dashboard overview for /admin/events."""

    def __init__(self, event_bus: EventBusProtocol | None = None) -> None:
        self._event_bus = event_bus

    async def handle(self, request: Any) -> PageContent:
        subscriber_count: str | int = "N/A"
        max_concurrent: str | int = "N/A"
        enable_dead_letter: str | bool = "N/A"
        error_count: str | int = "N/A"
        in_flight: str | int = "N/A"
        dead_letter_count: str | int = "N/A"

        if self._event_bus is not None:
            config = getattr(self._event_bus, "_config", None)
            if config is not None:
                max_concurrent = getattr(config, "max_concurrent_handlers", "N/A")
                enable_dead_letter = getattr(config, "enable_dead_letter", "N/A")

            try:
                subscribers = getattr(self._event_bus, "_subscribers", {})
                subscriber_count = len(subscribers)
            except Exception:
                subscriber_count = "N/A"

            try:
                # Diagnostics are an optional public capability.  A custom
                # EventBusProtocol without it reports no retained errors;
                # private bus state is intentionally not inspected here.
                dispatch_errors = getattr(self._event_bus, "dispatch_errors", ())
                error_count = len(dispatch_errors)
            except Exception:
                error_count = "N/A"

            try:
                in_flight = getattr(self._event_bus, "_in_flight", 0)
            except Exception:
                in_flight = "N/A"

            try:
                dl_store = getattr(self._event_bus, "dead_letter_store", None)
                if dl_store is not None:
                    get_count = getattr(dl_store, "get_count", None)
                    if get_count is not None:
                        dead_letter_count = await get_count()
            except Exception:
                dead_letter_count = "N/A"

        return PageContent(
            title="Events",
            body=StatContent(
                stats=(
                    Stat(
                        label="Subscribers",
                        value=str(subscriber_count),
                        icon="users",
                    ),
                    Stat(
                        label="In-Flight",
                        value=str(in_flight),
                        icon="activity",
                    ),
                    Stat(
                        label="Dead-Letter Count",
                        value=str(dead_letter_count),
                        icon="alert-triangle",
                    ),
                    Stat(
                        label="Errors",
                        value=str(error_count),
                        icon="x-circle",
                    ),
                    Stat(
                        label="Status",
                        value="Connected"
                        if self._event_bus is not None
                        else "Unavailable",
                        icon="activity",
                    ),
                    Stat(
                        label="Max Concurrent Handlers",
                        value=str(max_concurrent),
                        icon="activity",
                    ),
                    Stat(
                        label="Dead Letter Enabled",
                        value=str(enable_dead_letter),
                        icon="alert-triangle",
                    ),
                )
            ),
        )
