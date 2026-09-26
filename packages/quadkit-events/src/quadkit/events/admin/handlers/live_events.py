"""Live events widget handler — reactive feed of the latest domain events."""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

from quadkit.contracts.admin import TableCell, TableContent, WidgetParams
from quadkit.contracts.admin.errors import AdminError
from quadkit.events.messages.event import Event
from quadkit.events.reactive import from_store
from quadkit.events.stores.base import AbstractEventStore
from quadkit.reactive import ops
from quadkit.result import Ok, Result

if TYPE_CHECKING:
    from quadkit.events.streaming.dispatcher import StreamDispatcher


class LiveEventsWidgetHandler:
    """Widget handler streaming the most recent domain events.

    Catch-up history is replayed from the event store once at startup;
    with a ``StreamDispatcher`` the handler subscribes immediately (in
    ``__init__``, before any event can be missed) and tails live events
    into a bounded cache that ``get_data`` drains without blocking.

    Note:
        Requires an active event loop at construction.
    """

    def __init__(
        self,
        event_store: AbstractEventStore,
        dispatcher: StreamDispatcher | None = None,
    ) -> None:
        self._store = event_store
        self._dispatcher = dispatcher
        self._cache: deque[Event] = deque(maxlen=50)
        if dispatcher is not None:
            dispatcher.subscribe_all(self._on_live_event)

    async def _on_live_event(self, event: Event) -> None:
        self._cache.append(event)

    async def get_data(self, params: WidgetParams) -> Result[TableContent, AdminError]:
        """Fetch up to 10 recent events as a table.

        Catch-up history is replayed from the event store at startup;
        live events tailed from the dispatcher (when configured) are
        appended on top.

        Args:
            params: Widget request parameters (unused by this handler).

        Returns:
            Result containing TableContent with Type/Aggregate/Actor rows.
        """
        rows: list[tuple[TableCell, TableCell, TableCell]] = []
        seen: set[Any] = set()

        async def _append(event: Any) -> None:
            key = (
                event.correlation_id
                if getattr(event, "correlation_id", None) is not None
                else f"{event.event_type}:{getattr(event, 'aggregate_id', '')}"
            )
            if key in seen or len(rows) >= 10:
                return
            seen.add(key)
            rows.append(
                (
                    TableCell(text=str(event.event_type)),
                    TableCell(text=str(getattr(event, "aggregate_id", ""))),
                    TableCell(text=str(getattr(event, "actor_id", "") or "")),
                )
            )

        for event in list(self._cache):
            await _append(event)

        async def _drain(stream: Any) -> None:
            async for event in stream:
                await _append(event)

        await _drain(from_store(self._store).pipe(ops.take(10)))

        return Ok(
            TableContent(
                columns=("Type", "Aggregate", "Actor"),
                rows=tuple(rows),
                empty_message="No events yet.",
            )
        )


__all__ = ["LiveEventsWidgetHandler"]
