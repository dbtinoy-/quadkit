"""Event stream cursor/iterator utilities.

Extracted from ``stores/base.py`` (M-01 split). Contains the polling-based
subscription, type-filtered streaming, event replay, and checkpoint helpers
that all ``AbstractEventStore`` implementations inherit via
:class:`EventStreamMixin`.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from datetime import datetime

    from quadkit.events.messages.event import Event
    from quadkit.events.stores.base import StoredEvent

logger = get_logger(__name__)

__all__ = ["EventStreamMixin"]


class EventStreamMixin:
    """Mixin that adds stream/cursor/replay methods to an event store.

    Concrete subclasses must provide ``stream_all`` and ``stream_by_type``.
    The mixin relies exclusively on those two primitives; it never accesses
    storage directly.

    Usage::

        class MyStore(AbstractEventStore, EventStreamMixin):
            async def stream_all(self, ...) -> AsyncIterator[Event]:
                ...
    """

    if TYPE_CHECKING:
        # Type-checker stubs — never executed at runtime.
        def stream_all(
            self,
            from_position: int = 0,
            batch_size: int = 100,
            partition: int | None = None,
            total_partitions: int | None = None,
        ) -> AsyncIterator[Event]:
            """Abstract — implemented by the concrete store."""
            ...  # pragma: no cover

        def stream_by_type(
            self,
            event_types: list[str],
            from_position: int = 0,
        ) -> AsyncIterator[Event]:
            """Abstract — implemented by the concrete store."""
            ...  # pragma: no cover

    async def subscribe(
        self,
        from_position: int = 0,
        batch_size: int = 100,
        event_types: list[str] | None = None,
    ) -> AsyncIterator[Event]:
        """Subscribe to all events from a position (M-06).

        Catches up from history then polls for new events. The default
        implementation is polling-based; override for push-based stores.

        Args:
            from_position: Starting global sequence number.
            batch_size: Events per catch-up batch.
            event_types: Optional list of event types to filter.

        Yields:
            Events in order as they are discovered.
        """
        position = from_position
        while True:
            found_any = False
            stream: AsyncIterator[Event] = (
                self.stream_by_type(event_types, position)
                if event_types
                else self.stream_all(position, batch_size)
            )
            async for event in stream:
                yield event
                # M-05: sequence_number/global_sequence used for position.
                pos = getattr(event, "sequence_number", None) or getattr(
                    event, "global_sequence", None
                )
                if pos:
                    position = pos
                found_any = True

            if not found_any:
                await asyncio.sleep(1.0)

    async def find_events_since(
        self,
        checkpoint: int | datetime = 0,
        limit: int = 100,
    ) -> list[Event]:
        """Get events since a checkpoint (global position or timestamp).

        Args:
            checkpoint: Global position (int) or timestamp (datetime).
            limit: Maximum number of events to return.

        Returns:
            List of events.
        """
        events: list[Event] = []

        if isinstance(checkpoint, (int, float)):
            async for event in self.stream_all(
                from_position=int(checkpoint), batch_size=limit
            ):
                events.append(event)
                if len(events) >= limit:
                    break
        else:
            async for event in self.stream_all(from_position=0, batch_size=limit):
                if event.occurred_at >= checkpoint:
                    events.append(event)
                    if len(events) >= limit:
                        break

        return events

    async def get_stored_events_since(
        self,
        global_sequence: int = 0,
        *,
        limit: int = 1000,
    ) -> list[StoredEvent]:
        """Return low-level StoredEvent objects since a global sequence.

        Args:
            global_sequence: Starting sequence (inclusive).
            limit: Maximum events to return.

        Returns:
            List of :class:`StoredEvent` instances.

        Raises:
            NotImplementedError: If the concrete store has not overridden this.
        """
        raise NotImplementedError("get_stored_events_since not implemented")

    async def replay_events(
        self,
        handler: Any,
        since: datetime | None = None,
        event_types: list[str] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> int:
        """Replay events through a handler in deterministic per-aggregate order.

        Events are collected, optionally filtered by *since* timestamp, then
        sorted by ``(aggregate_id, sequence_number)`` before dispatch.
        This guarantees causal order per aggregate regardless of global
        sequence ordering in the backend.

        Note:
            The full event set is buffered in memory. For very large stores,
            use ``subscribe`` with a checkpoint mechanism instead.

        Args:
            handler: Async callable that receives each :class:`Event`.
            since: Optional exclusive timestamp checkpoint.
            event_types: Optional list of event type names to include.
            on_progress: Optional callback invoked after each event: ``(processed, total)``.

        Returns:
            Number of events replayed.
        """
        logger.info("Starting event replay (since=%s, types=%s)", since, event_types)
        buffered: list[Event] = []
        try:
            event_iter: AsyncIterator[Event] = (
                self.stream_by_type(event_types) if event_types else self.stream_all()
            )
            async for event in event_iter:
                # ``since`` is an exclusive replay checkpoint: an event at
                # exactly the checkpoint has already been consumed.
                if since and event.occurred_at <= since:
                    continue
                buffered.append(event)
        except (RuntimeError, OSError, ValueError) as e:
            logger.exception("Replay stream failed", error=str(e))
            return 0

        buffered.sort(key=lambda e: (str(e.aggregate_id or ""), e.sequence_number or 0))

        count = 0
        total = len(buffered)
        try:
            for event in buffered:
                await handler(event)
                count += 1
                if on_progress is not None:
                    on_progress(count, total)
        except (RuntimeError, OSError, ValueError) as e:
            logger.exception(
                "Replay dispatch failed after %d events", count, error=str(e)
            )
        return count
