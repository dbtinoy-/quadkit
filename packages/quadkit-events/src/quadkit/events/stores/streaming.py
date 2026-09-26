"""Streaming Event Store decorator (N-05: full delegation).

N-05 fix: StreamingEventStore now fully delegates ALL AbstractEventStore methods to the
inner store. Explicit overrides exist for ``append`` (to intercept + stream) and
the small set of methods that change the decorator's own state. Every other
method is transparently proxied via ``__getattr__``, so swapping backends is
completely transparent to callers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.events.stores.base import (
    AbstractEventStore,
    AbstractEventStoreFactory,
    StoredEvent,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from datetime import datetime

    from quadkit.events.messages.event import Event

    class EventStream:
        """Stub for the (optional) streaming EventStream."""

        async def publish_event(self, event: Event) -> None: ...


class StreamingEventStore(AbstractEventStore):
    """AbstractEventStore decorator that automatically publishes events to an EventStream.

    All AbstractEventStore methods are fully delegated to the inner store.
    Only ``append`` is intercepted to also publish to the event stream.
    """

    def __init__(
        self,
        event_store: AbstractEventStore,
        event_stream: EventStream | None = None,
    ) -> None:
        # NOTE: intentionally do NOT call super().__init__() here so we
        # don't get an extra _schema_evolution attribute — all schema
        # logic belongs to the inner store.
        self._event_store = event_store
        self._event_stream = event_stream

    # ------------------------------------------------------------------ #
    # Interception point — append                                          #
    # ------------------------------------------------------------------ #

    async def append(
        self,
        stream_id: str,
        events: list[Event],
        expected_version: int | None = None,
    ) -> int:
        """Append events to the store and publish to stream if available."""
        new_version = await self._event_store.append(
            stream_id, events, expected_version
        )
        if self._event_stream:
            for event in events:
                await self._event_stream.publish_event(event)
        return new_version

    # ------------------------------------------------------------------ #
    # Explicit delegation for all AbstractEventStore abstract / concrete methods   #
    # ------------------------------------------------------------------ #

    async def read(
        self,
        stream_id: str,
        from_version: int = 0,
        to_version: int | None = None,
        limit: int | None = None,
    ) -> list[Event]:
        return await self._event_store.read(stream_id, from_version, to_version, limit)

    async def get_stream_version(self, stream_id: str) -> int:
        return await self._event_store.get_stream_version(stream_id)

    async def stream_exists(self, stream_id: str) -> bool:
        return await self._event_store.stream_exists(stream_id)

    async def get_stream_info(self, stream_id: str) -> Any:
        return await self._event_store.get_stream_info(stream_id)

    async def stream_all(
        self,
        from_position: int = 0,
        batch_size: int = 100,
        partition: int | None = None,
        total_partitions: int | None = None,
    ) -> AsyncIterator[Event]:
        async for event in self._event_store.stream_all(
            from_position, batch_size, partition, total_partitions
        ):
            yield event

    async def stream_by_type(
        self,
        event_types: list[str],
        from_position: int = 0,
    ) -> AsyncIterator[Event]:
        async for event in self._event_store.stream_by_type(event_types, from_position):
            yield event

    async def find_events_since(
        self,
        checkpoint: int | datetime = 0,
        limit: int = 100,
    ) -> list[Event]:
        return await self._event_store.find_events_since(checkpoint, limit)

    async def get_stored_events_since(
        self,
        global_sequence: int = 0,
        *,
        limit: int = 1000,
    ) -> list[StoredEvent]:
        return await self._event_store.get_stored_events_since(
            global_sequence, limit=limit
        )

    async def find_by_aggregate(self, aggregate_id: str) -> list[Event]:
        return await self._event_store.find_by_aggregate(aggregate_id)

    async def replay_events(
        self,
        handler: Any,
        since: datetime | None = None,
        event_types: list[str] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> int:
        return await self._event_store.replay_events(
            handler, since, event_types, on_progress
        )

    async def compact(self, stream_id: str, up_to_version: int) -> int:
        """Delegate compaction to the inner store."""
        return await self._event_store.compact(stream_id, up_to_version)

    async def close(self) -> None:
        await self._event_store.close()

    # ------------------------------------------------------------------ #
    # __getattr__ fallback — catches any extra methods on concrete stores  #
    # (e.g. InMemoryEventStore.clear, PostgresEventStore.health_check)     #
    # ------------------------------------------------------------------ #

    def __getattr__(self, name: str) -> Any:
        return getattr(self._event_store, name)

    # ------------------------------------------------------------------ #
    # Fluent configuration helpers                                         #
    # ------------------------------------------------------------------ #

    def with_stream(self, event_stream: EventStream) -> StreamingEventStore:
        """Configure the event stream for automatic publishing."""
        self._event_stream = event_stream
        return self

    def without_stream(self) -> StreamingEventStore:
        """Remove event stream configuration."""
        self._event_stream = None
        return self


class StreamingEventStoreFactory(AbstractEventStoreFactory):
    """Factory for streaming-enabled event stores."""

    def __init__(
        self,
        base_factory: AbstractEventStoreFactory,
        event_stream: EventStream | None = None,
    ) -> None:
        self._base_factory = base_factory
        self._event_stream = event_stream

    async def create_event_store(self) -> StreamingEventStore:
        """Create a streaming-enabled event store."""
        base_store = await self._base_factory.create_event_store()
        return StreamingEventStore(base_store, self._event_stream)

    def with_stream(self, event_stream: EventStream) -> StreamingEventStoreFactory:
        """Configure the event stream for automatic publishing."""
        self._event_stream = event_stream
        return self

    def without_stream(self) -> StreamingEventStoreFactory:
        """Remove event stream configuration."""
        self._event_stream = None
        return self
