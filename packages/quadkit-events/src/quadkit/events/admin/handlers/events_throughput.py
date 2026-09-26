"""Events throughput widget handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.contracts.admin import MessageContent, Tone, WidgetParams
from quadkit.contracts.admin.errors import AdminError
from quadkit.result import Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.events import EventBusProtocol


class EventsThroughputWidgetHandler:
    """Fetches events throughput data.

    Dependencies:
        event_bus: Injected EventBusProtocol instance.
    """

    def __init__(self, event_bus: EventBusProtocol) -> None:
        self._event_bus = event_bus

    async def get_data(
        self, params: WidgetParams
    ) -> Result[MessageContent, AdminError]:
        """Fetch event throughput metrics.

        Returns a message explaining stats are unavailable pending
        EventBusProtocol stats methods. Infrastructure failures
        propagate as exceptions.

        Args:
            params: Widget request parameters (contains time_window_minutes).

        Returns:
            Result containing MessageContent or AdminError.
        """
        return Ok(
            MessageContent(
                text=(
                    "Event throughput is not available — the EventBus "
                    "stats protocol does not expose counters yet."
                ),
                tone=Tone.DEFAULT,
            )
        )


__all__ = ["EventsThroughputWidgetHandler"]
