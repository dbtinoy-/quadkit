"""Redis-backed AbstractEventStore for lightweight deployments.

Uses quadkit-contracts StateStoreProtocol protocol for storage — no direct Redis dependency.
Key format:
  quadkit:events:{stream_id}:events  -> JSON list of serialized events
  quadkit:events:{stream_id}:version -> integer version
  quadkit:events:_streams            -> JSON list of known stream IDs
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any, cast

from quadkit import serialization as json
from quadkit.events.exceptions import ConcurrencyError
from quadkit.events.stores.base import AbstractEventStore
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from quadkit.contracts.infra.state import StateStoreProtocol
    from quadkit.events.messages.event import Event

logger = get_logger(__name__)


class RedisEventStore(AbstractEventStore):
    """Redis-backed AbstractEventStore for lightweight deployments.

    Uses the :class:`~quadkit.contracts.state.protocols.StateStoreProtocol` protocol
    for storage, so no direct Redis dependency is introduced into this package.
    Suitable for single-node or low-throughput deployments where a full
    relational or document store is not required.

    Key layout::

        {namespace}:{stream_id}:events  — JSON array of serialised event dicts
        {namespace}:{stream_id}:version — current integer version for the stream
        {namespace}:_streams            — JSON array of all known stream IDs

    Example::

        from quadkit.events.stores.redis import RedisEventStore

        store = RedisEventStore(state_store, namespace="myapp:events")
        await store.append("order-123", [OrderCreated(...)])
        events = await store.read("order-123")
    """

    def __init__(
        self,
        store: StateStoreProtocol,
        namespace: str = "quadkit:events",
    ) -> None:
        """Initialise the Redis-backed event store.

        Args:
            store: A :class:`~quadkit.contracts.state.protocols.StateStoreProtocol`
                instance (e.g. a Redis-backed implementation).
            namespace: Key prefix used for all stored keys.
        """
        super().__init__()
        self._store = store
        self._namespace = namespace

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    def _events_key(self, stream_id: str) -> str:
        return f"{self._namespace}:{stream_id}:events"

    def _version_key(self, stream_id: str) -> str:
        return f"{self._namespace}:{stream_id}:version"

    @property
    def _index_key(self) -> str:
        return f"{self._namespace}:_streams"

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def _serialize_event(self, event: Event) -> dict[str, Any]:
        """Serialise an event to a JSON-safe dict."""
        if hasattr(event, "model_dump"):
            data: dict[str, Any] = event.model_dump(mode="json")
            return data
        return dataclasses.asdict(event)

    def _deserialize_event(self, data: dict[str, Any]) -> Event:
        """Reconstruct an :class:`~quadkit.events.messages.event.Event` from a dict.

        Note: UUID and datetime fields are kept as strings (as produced by
        ``model_dump(mode="json")``) which is acceptable for lightweight
        deployments. Use PostgreSQL or MongoDB stores when strict typing is
        required.
        """
        from quadkit.events.messages.event import Event as _Event

        return _Event(**data)

    # ------------------------------------------------------------------
    # Stream index helpers
    # ------------------------------------------------------------------

    async def _get_stream_ids(self) -> list[str]:
        """Return all known stream IDs from the global index."""
        raw = await self._store.get(self._index_key)
        if raw is None:
            return []
        if isinstance(raw, str):
            return cast("list[str]", json.loads(raw))
        return list(raw)

    async def _register_stream(self, stream_id: str) -> None:
        """Add *stream_id* to the global index if not already present."""
        ids = await self._get_stream_ids()
        if stream_id not in ids:
            ids.append(stream_id)
            await self._store.set(self._index_key, json.dumps(ids))

    # ------------------------------------------------------------------
    # Core operations (abstract method implementations)
    # ------------------------------------------------------------------

    async def append(
        self,
        stream_id: str,
        events: list[Event],
        expected_version: int | None = None,
    ) -> int:
        """Append *events* to *stream_id* with optimistic concurrency control.

        Args:
            stream_id: Unique stream identifier.
            events: Events to append.  Empty list is a no-op.
            expected_version: If provided, the current stream version must
                equal this value or :class:`~quadkit.events.exceptions.ConcurrencyError`
                is raised.

        Returns:
            New stream version after the append.

        Raises:
            ConcurrencyError: If *expected_version* does not match the actual
                current version of the stream.
        """
        if not events:
            return await self.get_stream_version(stream_id)

        current_version = await self.get_stream_version(stream_id)

        if expected_version is not None and current_version != expected_version:
            raise ConcurrencyError(
                stream_id=stream_id,
                expected_version=expected_version,
                actual_version=current_version,
            )

        # Load existing serialised event dicts.
        raw = await self._store.get(self._events_key(stream_id))
        existing: list[dict[str, Any]] = []
        if raw is not None:
            existing = cast(
                "list[dict[str, Any]]",
                json.loads(raw) if isinstance(raw, str) else list(raw),
            )

        # Stamp each incoming event with its new sequential version and
        # serialise it for storage.
        new_version = current_version
        serialized: list[dict[str, Any]] = list(existing)
        for event in events:
            new_version += 1
            versioned: Event = event.with_version(new_version)
            serialized.append(self._serialize_event(versioned))

        await self._store.set(self._events_key(stream_id), json.dumps(serialized))
        await self._store.set(self._version_key(stream_id), json.dumps(new_version))
        await self._register_stream(stream_id)

        logger.debug(
            "redis_events_appended",
            stream_id=stream_id,
            count=len(events),
            new_version=new_version,
        )
        return new_version

    async def read(
        self,
        stream_id: str,
        from_version: int = 0,
        to_version: int | None = None,
        limit: int | None = None,
    ) -> list[Event]:
        """Read events from *stream_id*.

        Args:
            stream_id: Stream to read from.
            from_version: Lowest version to include (inclusive, default 0 = all).
            to_version: Highest version to include (inclusive).
            limit: Maximum number of events to return.

        Returns:
            Ordered list of :class:`~quadkit.events.messages.event.Event` objects.
        """
        raw = await self._store.get(self._events_key(stream_id))
        if raw is None:
            return []

        all_data: list[dict[str, Any]] = cast(
            "list[dict[str, Any]]",
            json.loads(raw) if isinstance(raw, str) else list(raw),
        )

        events: list[Event] = [
            self._deserialize_event(d)
            for d in all_data
            if d.get("version", 0) >= from_version
            and (to_version is None or d.get("version", 0) <= to_version)
        ]

        if limit is not None:
            events = events[:limit]

        return events

    async def load(self, stream_id: str, after_version: int = 0) -> list[Event]:
        """Load events after *after_version* (non-inclusive lower bound).

        This alias is used by several base-class helpers.

        Args:
            stream_id: Stream to load events from.
            after_version: Events with version <= this value are excluded.

        Returns:
            Ordered list of events.
        """
        from_v = after_version + 1 if after_version > 0 else 0
        return await self.read(stream_id, from_version=from_v)

    async def get_stream_version(self, stream_id: str) -> int:
        """Return the current version of *stream_id* (0 if the stream is empty).

        Args:
            stream_id: Stream identifier.

        Returns:
            Current integer version.
        """
        raw = await self._store.get(self._version_key(stream_id))
        if raw is None:
            return 0
        if isinstance(raw, str):
            return int(json.loads(raw))
        return int(raw)

    async def get_version(self, stream_id: str) -> int:
        """Public alias for :meth:`get_stream_version`.

        Args:
            stream_id: Stream identifier.

        Returns:
            Current integer version.
        """
        return await self.get_stream_version(stream_id)

    async def stream_all(
        self,
        from_position: int = 0,
        batch_size: int = 100,
        partition: int | None = None,
        total_partitions: int | None = None,
    ) -> AsyncIterator[Event]:
        """Stream all events across all known streams.

        Note: Cross-stream global ordering is *not* guaranteed by this
        implementation.  Streams are iterated in registration order and events
        within each stream are returned in version order.  For strict
        global ordering, use the PostgreSQL or MongoDB stores.

        Args:
            from_position: Events with ``sequence_number`` <= this value are
                skipped.
            batch_size: Unused; present for interface compatibility.
            partition: Optional partition index for sharding.
            total_partitions: Total number of partitions.

        Yields:
            Events in stream-registration order, version order within each stream.
        """
        import hashlib

        _ = batch_size
        stream_ids = await self._get_stream_ids()
        for stream_id in stream_ids:
            if partition is not None and total_partitions is not None:
                h = int(
                    hashlib.md5(stream_id.encode(), usedforsecurity=False).hexdigest()[
                        :8
                    ],
                    16,
                )
                if h % total_partitions != partition:
                    continue

            for event in await self.read(stream_id):
                seq = getattr(event, "sequence_number", None) or 0
                if seq > from_position:
                    yield event

    async def compact(self, stream_id: str, up_to_version: int) -> int:
        """Purge events for *stream_id* up to and including *up_to_version*.

        Args:
            stream_id: Stream to compact.
            up_to_version: Events at or below this version are removed.

        Returns:
            Number of events deleted.
        """
        raw = await self._store.get(self._events_key(stream_id))
        if raw is None:
            return 0

        all_data: list[dict[str, Any]] = cast(
            "list[dict[str, Any]]",
            json.loads(raw) if isinstance(raw, str) else list(raw),
        )

        remaining = [d for d in all_data if d.get("version", 0) > up_to_version]
        deleted = len(all_data) - len(remaining)

        if deleted > 0:
            await self._store.set(
                self._events_key(stream_id),
                json.dumps(remaining),
            )
            logger.debug(
                "redis_events_compacted",
                stream_id=stream_id,
                deleted=deleted,
                up_to_version=up_to_version,
            )

        return deleted

    async def close(self) -> None:
        """Close the event store.

        No-op for this implementation; the underlying :class:`StateStoreProtocol` manages
        its own lifecycle.
        """
        return


__all__ = ["RedisEventStore"]
