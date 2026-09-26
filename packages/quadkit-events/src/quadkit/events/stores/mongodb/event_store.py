"""
MongoDB event store implementation.

Migrated to use ``DocumentStoreProtocol`` from ``the optional provider``
for connection lifecycle and collection access while retaining
motor-specific operations (change streams, sessions) where needed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from typing import TYPE_CHECKING, Any

from quadkit.events.exceptions import ConcurrencyError
from quadkit.events.stores.base import AbstractEventStore
from quadkit.events.stores.mongodb.utils import deserialize_event, serialize_event
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from quadkit.contracts.data import CollectionProtocol, DocumentStoreProtocol
    from quadkit.events.messages.event import Event

logger = get_logger(__name__)


class MongoDBEventStore(AbstractEventStore):
    """MongoDB event store implementation using ``DocumentStoreProtocol``.

    Uses the ``the optional provider`` collection abstraction for standard CRUD
    while keeping direct motor access for change streams and transactions.

    Features:
        - Optimistic concurrency with version checking
        - Global event ordering with sequence counters
        - Efficient event streaming with cursors
        - Automatic index creation
        - Change streams support for real-time events

    Example:
        ```python
        store = MongoDBEventStore(document_store, config)
        await store.connect()

        try:
            await store.save("order-123", [event], expected_version=0)
        finally:
            await store.close()
        ```
    """

    def __init__(
        self,
        document_store: DocumentStoreProtocol,
        config: Any,
        event_serializer: Any | None = None,
    ) -> None:
        """Initialize MongoDB event store.

        Args:
            document_store: A connected ``DocumentStoreProtocol`` (e.g. MongoDBDocumentStore).
            config: Event store configuration with collection names.
            event_serializer: Optional custom event serializer.
        """
        self._store = document_store
        self.config = config
        self.event_serializer = event_serializer
        self._events: CollectionProtocol | None = None
        self._counters: CollectionProtocol | None = None
        self._connected = False

    @property
    def events(self) -> CollectionProtocol:
        """Events collection."""
        if self._events is None:
            raise RuntimeError("MongoDBEventStore is not connected")
        return self._events

    @property
    def counters(self) -> CollectionProtocol:
        """Counters collection."""
        if self._counters is None:
            raise RuntimeError("MongoDBEventStore is not connected")
        return self._counters

    async def connect(self) -> None:
        """Connect to MongoDB and set up collections."""
        if not self._store.is_connected():
            await self._store.connect()

        self._events = self._store.collection(self.config.events_collection)
        self._counters = self._store.collection(self.config.counters_collection)

        if self.config.auto_create_indexes:
            await self._create_indexes()

        self._connected = True
        logger.info("MongoDB event store connected")

    async def _create_indexes(self) -> None:
        """Create indexes for efficient querying."""
        await self.events.create_index(
            [("stream_id", 1), ("stream_version", 1)],
            unique=True,
        )
        await self.events.create_index([("global_sequence", 1)])
        await self.events.create_index([("event_type", 1)])
        await self.events.create_index([("timestamp", 1)])

    async def _get_next_sequence(self) -> int:
        """Get the next global sequence number."""
        result = await self.counters.find_one_and_update(
            {"_id": "global_sequence"},
            {"$inc": {"value": 1}},
            upsert=True,
            return_document=True,
        )
        if result is None:
            raise RuntimeError("Failed to get next sequence number")
        return int(result["value"])

    async def append(
        self,
        stream_id: str,
        events: list[Event],
        expected_version: int | None = None,
    ) -> int:
        """Append events to a stream with optimistic concurrency.

        Args:
            stream_id: Stream identifier.
            events: Events to save.
            expected_version: Expected current version.

        Returns:
            New stream version.

        Raises:
            ConcurrencyError: If version conflict occurs.
        """
        if not events:
            return await self.get_stream_version(stream_id)

        # Use DocumentStoreProtocol session for transaction
        async with self._store.session() as session:
            # Check current version within session
            current_version = await self.get_stream_version(stream_id)
            if expected_version is not None and current_version != expected_version:
                raise ConcurrencyError(stream_id, expected_version, current_version)

            # Prepare documents
            documents = []
            new_version = current_version

            for i, event in enumerate(events):
                version = current_version + i + 1
                global_seq = await self._get_next_sequence()

                event_id = getattr(event, "id", None) or getattr(
                    event, "event_id", None
                )
                doc = {
                    "global_sequence": global_seq,
                    "stream_id": stream_id,
                    "stream_version": version,
                    "event_id": str(event_id) if event_id else None,
                    "event_type": type(event).__name__,
                    "event_data": serialize_event(event, self.event_serializer),
                    "metadata": getattr(event, "metadata", {}),
                    "timestamp": getattr(event, "timestamp", datetime.now(UTC)),
                }
                documents.append(doc)
                new_version = version

            # Insert events
            try:
                await self.events.insert_many(documents)
            except Exception as e:  # noqa: BLE001 — inspects exception message for MongoDB duplicate key; re-raises as ConcurrencyError or plain
                if "duplicate key" in str(e).lower() or "E11000" in str(e):
                    # ``expected_version`` may legitimately be 0 (fresh
                    # stream), so test for None rather than truthiness.
                    expected = (
                        expected_version
                        if expected_version is not None
                        else current_version
                    )
                    raise ConcurrencyError(
                        stream_id,
                        expected,
                        expected + 1,
                    ) from e
                raise

        return new_version

    async def read(
        self,
        stream_id: str,
        from_version: int = 0,
        to_version: int | None = None,
        limit: int | None = None,
    ) -> list[Event]:
        """Read events from a stream."""
        query: dict[str, Any] = {
            "stream_id": stream_id,
            "stream_version": {"$gte": from_version},
        }
        if to_version is not None:
            query["stream_version"]["$lte"] = to_version

        events_list: list[Event] = []
        async for doc in await self.events.find(
            query,
            sort=[("stream_version", 1)],
            limit=limit or 0,
        ):
            events_list.append(deserialize_event(doc, self.event_serializer))

        return await self._apply_upcasting(events_list)

    async def get_stream_version(self, stream_id: str) -> int:
        """Get current stream version.

        Args:
            stream_id: Stream to check.

        Returns:
            Current version (0 if stream doesn't exist).
        """
        doc = await self.events.find_one(
            {"stream_id": stream_id},
        )
        # find_one doesn't support sort in the protocol, so use find with limit
        version = 0
        async for d in await self.events.find(
            {"stream_id": stream_id},
            sort=[("stream_version", -1)],
            limit=1,
        ):
            version = int(d["stream_version"])
        return version

    async def stream_all(
        self,
        from_position: int = 0,
        batch_size: int = 100,
        partition: int | None = None,
        total_partitions: int | None = None,
    ) -> AsyncIterator[Event]:
        """Stream all events from a global position."""
        async for doc in await self.events.find(
            {"global_sequence": {"$gt": from_position}},
            sort=[("global_sequence", 1)],
        ):
            event = deserialize_event(doc, self.event_serializer)
            migrated = await self._apply_upcasting([event])
            yield migrated[0]

    async def stream_by_type(
        self,
        event_types: list[str],
        from_position: int = 0,
    ) -> AsyncIterator[Event]:
        """Stream events filtered by type."""
        async for doc in await self.events.find(
            {
                "global_sequence": {"$gt": from_position},
                "event_type": {"$in": event_types},
            },
            sort=[("global_sequence", 1)],
        ):
            event = deserialize_event(doc, self.event_serializer)
            migrated = await self._apply_upcasting([event])
            yield migrated[0]

    async def watch_events(
        self,
        event_types: list[str] | None = None,
    ) -> AsyncIterator[Event]:
        """Watch for new events using MongoDB change streams.

        Note: This requires direct motor access for change stream support.
        Falls back to polling if the underlying store doesn't support
        ``watch()``.

        Args:
            event_types: Optional list of event types to filter.

        Yields:
            New events as they are inserted.
        """
        # Access raw motor collection for change stream support
        if not hasattr(self.events, "_col"):
            raise NotImplementedError(
                "watch_events requires a MongoDBCollection with motor backend"
            )

        raw_col = self.events._col

        pipeline: list[dict[str, Any]] = [{"$match": {"operationType": "insert"}}]
        if event_types:
            pipeline.append(
                {"$match": {"fullDocument.event_type": {"$in": event_types}}},
            )

        async with raw_col.watch(pipeline) as stream:
            async for change in stream:
                doc = change["fullDocument"]
                yield deserialize_event(doc, self.event_serializer)

    async def find_by_type(
        self,
        event_type: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Event]:
        """Get events of a specific type.

        Args:
            event_type: Event type name.
            limit: Maximum events to return.
            offset: Number of events to skip.

        Returns:
            List of events.
        """
        events_list: list[Event] = []
        async for doc in await self.events.find(
            {"event_type": event_type},
            sort=[("global_sequence", 1)],
            skip=offset,
            limit=limit,
        ):
            events_list.append(deserialize_event(doc, self.event_serializer))
        return events_list

    async def get_events_count(self, stream_id: str | None = None) -> int:
        """Get total event count.

        Args:
            stream_id: Optional stream to count (None for all).

        Returns:
            Event count.
        """
        query = {"stream_id": stream_id} if stream_id else {}
        return await self.events.count_documents(query)

    async def delete_stream(self, stream_id: str) -> int:
        """Delete all events for a stream.

        Args:
            stream_id: Stream to delete.

        Returns:
            Number of deleted events.
        """
        result = await self.events.delete_many({"stream_id": stream_id})
        return result.matched_count

    async def compact(self, stream_id: str, up_to_version: int) -> int:
        """Purge events for a stream up to (and including) the given version (MF-04).

        Args:
            stream_id: Stream to compact.
            up_to_version: Maximum version to delete.

        Returns:
            Number of events purged.
        """
        result = await self.events.delete_many(
            {
                "stream_id": stream_id,
                "stream_version": {"$lte": up_to_version},
            }
        )
        return result.matched_count

    async def close(self) -> None:
        """Close the MongoDB connection."""
        # Don't disconnect the store — it may be shared
        self._events = None
        self._counters = None
        self._connected = False
        logger.info("MongoDB event store disconnected")

    async def __aenter__(self) -> MongoDBEventStore:
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Async context manager exit."""
        await self.close()
