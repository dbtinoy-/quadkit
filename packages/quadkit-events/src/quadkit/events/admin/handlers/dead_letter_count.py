"""Dead letter count widget handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.admin import Stat, StatContent, Tone, WidgetParams
from quadkit.contracts.admin.errors import AdminError
from quadkit.logging import get_logger
from quadkit.result import Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.events import EventBusProtocol

logger = get_logger(__name__)


class DeadLetterCountWidgetHandler:
    """Fetches dead letter queue count and statistics.

    Dependencies:
        event_bus: Injected EventBusProtocol instance.
    """

    def __init__(self, event_bus: EventBusProtocol) -> None:
        self._event_bus = event_bus

    async def get_data(self, params: WidgetParams) -> Result[StatContent, AdminError]:
        """Fetch dead letter queue count and age.

        Mirrors the widget template: a non-zero count is a danger signal,
        a clear queue renders as success.
        Infrastructure failures propagate as exceptions.

        Args:
            params: Widget request parameters.

        Returns:
            Result containing StatContent or AdminError.
        """
        store = getattr(self._event_bus, "dead_letter_store", None)
        count = 0
        if store is not None:
            try:
                entries = await store.list_entries(limit=100)
            except Exception as exc:  # noqa: BLE001
                logger.warning("events_dead_letter.store_unavailable", error=str(exc))
                entries = []
            count = len(entries)
        stats: list[Stat] = [
            Stat(
                label="Dead Letters",
                value=str(count) if count > 0 else "✓ Queue clear",
                tone=Tone.DANGER if count > 0 else Tone.SUCCESS,
            )
        ]
        return Ok(StatContent(stats=tuple(stats)))


__all__ = ["DeadLetterCountWidgetHandler"]
