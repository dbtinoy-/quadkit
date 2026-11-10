"""SQLite event store implementation.

This module provides the SqliteEventStore class for event sourcing
with SQLite backend using the generic database provider.
"""

from __future__ import annotations

from copy import copy
from datetime import UTC, datetime
from hashlib import md5
from types import TracebackType
from typing import TYPE_CHECKING, Any

from quadkit.contracts.domain import DomainEvent
from quadkit.events.config import SqliteConfig
from quadkit.events.exceptions import ConcurrencyError, EventStoreError
from quadkit.events.stores._history import validated_stream_version
from quadkit.events.stores.base import AbstractEventStore
from quadkit.events.stores.sqlite.queries import SqliteQueries
from quadkit.events.stores.sqlite.serializer import (
    SqliteEventSerializer,
    validate_event_identity,
)
from quadkit.logging import get_logger
from quadkit.serialization import dumps

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from quadkit.contracts.data.sql.database import DatabaseProviderProtocol
    from quadkit.events.messages.event import Event
    from quadkit.events.types import StreamInfo

logger = get_logger(__name__)


class SqliteEventStore(AbstractEventStore):
    """SQLite event store implementation.

    This store uses the generic DatabaseProviderProtocol for async database access.
    Suitable for development, testing, and single-instance deployments.
    """

    def __init__(
        self,
        config: SqliteConfig | None = None,
        provider: DatabaseProviderProtocol | None = None,
        event_serializer: Any | None = None,
    ) -> None:
        """Initialize SQLite event store.

        Args:
            config: SQLite configuration.
            provider: The generic database provider injected via DI.
            event_serializer: Optional custom event serializer.
        """
        super().__init__()
        self.config = config or SqliteConfig()
        if provider is None:
            raise ValueError("provider (DatabaseProviderProtocol) is required")
        self.provider = provider
        self.serializer = SqliteEventSerializer(event_serializer)
        self.queries = SqliteQueries(self.config)
        self._connected = False

    def register_event_type(self, event_type: str, event_class: type) -> None:
        """Register an event type for proper deserialization."""
        self.serializer.register_event_type(event_type, event_class)

    async def connect(self) -> None:
        """Connection is managed by the provider. Tables are created if configured."""
        self._connected = False
        if self.config.auto_create_tables:
            await self._create_tables()

        try:
            state_schema = await self.provider.execute_query(
                self.queries.get_check_stream_state_sql()
            )
        except Exception as exc:
            raise EventStoreError(
                "SQLite event stream-state schema is unavailable"
            ) from exc
        if not state_schema.success:
            raise EventStoreError("SQLite event stream-state schema is unavailable")

        self._connected = True
        logger.info("SQLite event store connected via provider")

    async def _create_tables(self) -> None:
        """Create events table if it doesn't exist."""
        ddl = self.queries.get_create_events_table_sql()

        for statement in ddl.split(";"):
            if statement.strip():
                result = await self.provider.execute_query(statement)
                if not result.success:
                    raise EventStoreError("Could not create SQLite event schema")

    async def append(
        self,
        stream_id: str,
        events: list[Event],
        expected_version: int | None = None,
    ) -> int:
        """Append events to a stream with optimistic concurrency."""
        if not events:
            return await self.get_stream_version(stream_id)

        async with self.provider.transaction():
            return await self._write_events(stream_id, events, expected_version)

    async def _write_events(
        self,
        stream_id: str,
        events: list[Event],
        expected_version: int | None = None,
    ) -> int:
        """Write events using the currently active provider transaction.

        Must be called within an active ``provider.transaction()`` context.
        Does not manage its own transaction boundary — the caller is responsible
        for wrapping this in a transaction for atomicity.

        Args:
            stream_id: Target event stream identifier.
            events: Events to append.
            expected_version: Optimistic concurrency version check.

        Returns:
            New stream version after appending.
        """
        current_version = await self.get_stream_version(stream_id)

        if expected_version is not None and current_version != expected_version:
            raise ConcurrencyError(
                stream_id=stream_id,
                expected_version=expected_version,
                actual_version=current_version,
            )

        new_version = current_version

        try:
            for i, event in enumerate(events):
                version = current_version + i + 1
                event_data = self.serializer.serialize_event(event)
                timestamp = (
                    event.timestamp
                    if hasattr(event, "timestamp")
                    else datetime.now(UTC)
                )
                event_id = getattr(event, "id", None) or getattr(
                    event,
                    "event_id",
                    None,
                )
                if not self.serializer.event_serializer and isinstance(
                    event, DomainEvent
                ):
                    validate_event_identity(event_data, event_id)
                metadata = getattr(event, "metadata", {})
                if hasattr(metadata, "model_dump"):
                    metadata = metadata.model_dump(mode="json")

                result = await self.provider.execute(
                    self.queries.get_insert_event_sql(),
                    [
                        stream_id,
                        version,
                        str(event_id),
                        type(event).__name__,
                        dumps(event_data).decode("utf-8")
                        if isinstance(dumps(event_data), bytes)
                        else dumps(event_data),
                        dumps(metadata).decode("utf-8")
                        if isinstance(dumps(metadata), bytes)
                        else dumps(metadata),
                        timestamp.isoformat(),
                    ],
                )
                if not result.success:
                    raise EventStoreError("Could not write event")
                new_version = version
        except Exception as exc:  # noqa: BLE001 — maps the UNIQUE(stream_id, stream_version) backstop violation to the framework's conflict type
            if (
                "UNIQUE constraint failed" in str(exc)
                or type(exc).__name__ == "IntegrityError"
            ):
                # ``expected_version`` may legitimately be 0 (fresh stream),
                # so test for None rather than truthiness.
                raise ConcurrencyError(
                    stream_id=stream_id,
                    expected_version=(
                        expected_version
                        if expected_version is not None
                        else current_version
                    ),
                    actual_version=new_version,
                ) from exc
            raise

        return new_version

    async def read(
        self,
        stream_id: str,
        from_version: int = 0,
        to_version: int | None = None,
        limit: int | None = None,
    ) -> list[Event]:
        """Read events from a stream (M-15)."""

        query = self.queries.get_read_events_sql(to_version, limit)
        args: list[Any] = [stream_id, from_version]

        if to_version is not None:
            args.append(to_version)
        if limit is not None:
            args.append(limit)

        # Read bounds and rows in one provider transaction to avoid returning
        # a partial history if compaction races this read.
        async with self.provider.transaction():
            _, compacted_through = await self._stream_bounds(stream_id)
            start = max(1, from_version)
            if (
                limit != 0
                and (to_version is None or to_version >= start)
                and start <= compacted_through
            ):
                raise EventStoreError("SQLite event history was compacted")
            result = await self.provider.execute_query(query, args)
            if not result.success:
                raise EventStoreError("Could not read SQLite event stream")
            events = [self.serializer.deserialize_event(row) for row in result.rows]

        # M-03: Apply upcasting
        return await self._apply_upcasting(events)

    async def get_stream_version(self, stream_id: str) -> int:
        """Get the stream high-water version, including compacted events."""
        version, _ = await self._stream_bounds(stream_id)
        return version

    async def stream_exists(self, stream_id: str) -> bool:
        """Check the logical version, including a compacted stream's marker."""
        return await validated_stream_version(self, stream_id) > 0

    async def get_stream_info(self, stream_id: str) -> StreamInfo | None:
        """Report logical version and metadata of currently retained events."""
        from quadkit.events.types import StreamInfo

        async with self.provider.transaction():
            version, missing_prefix = await self._stream_bounds(stream_id)
            if version == 0:
                return None
            retained = version - missing_prefix
            if not retained:
                return StreamInfo(stream_id=stream_id, version=version, event_count=0)
            first = await self.read(stream_id, from_version=missing_prefix + 1, limit=1)
            last = (
                first
                if retained == 1
                else await self.read(stream_id, from_version=version, limit=1)
            )
            if (
                len(first) != 1
                or len(last) != 1
                or await self._stream_bounds(stream_id) != (version, missing_prefix)
            ):
                raise EventStoreError(
                    "SQLite event history changed during stream info read"
                )
            return StreamInfo(
                stream_id=stream_id,
                aggregate_type=first[0].aggregate_type,
                version=version,
                event_count=retained,
                created_at=first[0].occurred_at if missing_prefix == 0 else None,
                updated_at=last[0].occurred_at,
            )

    async def _stream_bounds(self, stream_id: str) -> tuple[int, int]:
        """Return (high-water version, unavailable prefix) from one SQL view."""
        result = await self.provider.execute_query(
            self.queries.get_stream_version_sql(), [stream_id, stream_id]
        )
        if not result.success or len(result.rows) != 1:
            raise EventStoreError("Could not read event stream version")
        row = result.rows[0]
        try:
            compacted = row["compacted_through"]
            first = row["min_version"]
            last = row["max_version"]
            count = row["event_count"]
            if (
                type(compacted) is not int
                or compacted < 0
                or type(last) is not int
                or last < 0
                or type(count) is not int
                or count < 0
            ):
                raise ValueError("invalid event bounds")
            if count == 0:
                if first is not None or last != 0:
                    raise ValueError("invalid empty event bounds")
                return compacted, compacted
            if (
                type(first) is not int
                or first < 1
                or first <= compacted
                or last < first
                or count != last - first + 1
            ):
                raise ValueError("inconsistent event history")
            # Older databases may have a partially deleted prefix but no marker.
            return last, max(compacted, first - 1)
        except (KeyError, TypeError, ValueError) as exc:
            raise EventStoreError("SQLite event history is inconsistent") from exc

    async def stream_all(
        self,
        from_position: int = 0,
        batch_size: int = 100,
        partition: int | None = None,
        total_partitions: int | None = None,
    ) -> AsyncIterator[Event]:
        """Stream events after a global position, optionally by stream partition.

        Partitioning scans ordered batches and hashes the stream ID in Python;
        SQLite does not provide the old query's STR_HASH function. It uses the
        same MD5-prefix rule as the memory and Redis stores, but does not imply
        partition compatibility with every backend or a custom SQLite UDF.
        """
        if type(batch_size) is not int or batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")
        if partition is not None or total_partitions is not None:
            if (
                type(partition) is not int
                or type(total_partitions) is not int
                or total_partitions <= 0
                or not 0 <= partition < total_partitions
            ):
                raise ValueError("invalid stream partition")

        position = from_position
        if not self._connected:
            await self.connect()

        while True:
            result = await self.provider.execute_query(
                self.queries.get_stream_all_sql(),
                [position, batch_size],
            )
            if not result.success:
                raise EventStoreError("Could not stream SQLite events")
            if not result.rows:
                break

            for row in result.rows:
                # Advance for every scanned row, including rows belonging to
                # other partitions, so a batch with no matches cannot loop.
                position = row["global_sequence"]
                if partition is not None and total_partitions is not None:
                    stream_hash = int(
                        md5(
                            row["stream_id"].encode(), usedforsecurity=False
                        ).hexdigest()[:8],
                        16,
                    )
                    if stream_hash % total_partitions != partition:
                        continue
                yield await self._stream_event(row)

    async def _stream_event(self, row: dict[str, Any]) -> Event:
        """Return an isolated upcast event carrying its actual global cursor."""
        event = self.serializer.deserialize_event(row)
        migrated = (await self._apply_upcasting([event]))[0]
        try:
            stamped = copy(migrated)
            if stamped is migrated:
                raise TypeError("event copy is not independent")
            object.__setattr__(stamped, "sequence_number", int(row["global_sequence"]))
            if stamped.sequence_number != int(row["global_sequence"]):
                raise TypeError("event did not retain stream position")
        except Exception as exc:  # noqa: BLE001 — an incompatible custom event cannot be checkpointed safely
            raise EventStoreError(
                "Could not attach SQLite event stream position"
            ) from exc
        return stamped

    async def stream_by_type(
        self,
        event_types: list[str],
        from_position: int = 0,
    ) -> AsyncIterator[Event]:
        """Stream events filtered by type."""
        query = self.queries.get_stream_by_type_sql(len(event_types))
        result = await self.provider.execute_query(
            query,
            [from_position, *event_types],
        )
        if not result.success:
            raise EventStoreError("Could not stream SQLite events by type")

        for row in result.rows:
            yield await self._stream_event(row)

    async def find_by_type(
        self,
        event_type: str,
        count: int = 100,
        start: int = 0,
    ) -> list[Event]:
        """Get events of a specific type."""
        result = await self.provider.execute_query(
            self.queries.find_by_type_sql(),
            [event_type, count, start],
        )
        if not result.success:
            raise EventStoreError("Could not find SQLite events by type")

        return [self.serializer.deserialize_event(row) for row in result.rows]

    async def get_events_count(self, stream_id: str | None = None) -> int:
        """Get total event count."""
        query = self.queries.get_events_count_sql(stream_id)
        if stream_id is not None:
            result = await self.provider.execute_query(query, [stream_id])
        else:
            result = await self.provider.execute_query(query)
        if not result.success:
            raise EventStoreError("Could not count SQLite events")

        return (
            int(
                result.rows[0]["count"]
                if "count" in result.rows[0]
                else next(iter(result.rows[0].values()))
            )
            if result.rows
            else 0
        )

    async def delete_stream(self, stream_id: str) -> int:
        """Delete all events for a stream."""
        async with self.provider.transaction():
            count = await self.get_events_count(stream_id)
            result = await self.provider.execute(
                self.queries.get_delete_stream_sql(),
                [stream_id],
            )
            if not result.success:
                raise EventStoreError("Could not delete SQLite event stream")
            state_result = await self.provider.execute(
                self.queries.get_delete_stream_state_sql(), [stream_id]
            )
            if not state_result.success:
                raise EventStoreError("Could not delete SQLite event stream state")
            if await self._stream_bounds(stream_id) != (0, 0):
                raise EventStoreError("Could not verify SQLite event stream deletion")
        return count

    async def get_stream_ids(self) -> list[str]:
        """Get all stream IDs in the store."""
        if not self._connected:
            await self.connect()

        result = await self.provider.execute_query(
            self.queries.get_all_stream_ids_sql()
        )
        if not result.success:
            raise EventStoreError("Could not read SQLite event stream IDs")
        return [
            row["stream_id"] if "stream_id" in row else next(iter(row.values()))
            for row in result.rows
        ]

    async def compact(self, stream_id: str, up_to_version: int) -> int:
        """Purge events for a stream up to (and including) the given version (MF-04)."""
        if type(up_to_version) is not int or up_to_version < 0:
            raise ValueError("up_to_version must be a non-negative integer")
        if not self._connected:
            await self.connect()

        async with self.provider.transaction():
            current_version, previous_prefix = await self._stream_bounds(stream_id)
            compacted_through = min(up_to_version, current_version)
            if compacted_through:
                marker = await self.provider.execute(
                    self.queries.get_record_compaction_sql(),
                    [stream_id, compacted_through],
                )
                if not marker.success:
                    raise EventStoreError("Could not record SQLite event compaction")
            result = await self.provider.execute_delete(
                self.config.events_table,
                "stream_id = ? AND stream_version <= ?",
                [stream_id, up_to_version],
            )
            expected_deleted = max(0, compacted_through - previous_prefix)
            if (
                not result.success
                or type(result.affected_rows) is not int
                or result.affected_rows != expected_deleted
            ):
                raise EventStoreError("Could not compact SQLite event stream")
            if compacted_through:
                marker_result = await self.provider.execute_query(
                    self.queries.get_compaction_marker_sql(), [stream_id]
                )
                if (
                    not marker_result.success
                    or len(marker_result.rows) != 1
                    or type(marker_result.rows[0].get("compacted_through")) is not int
                    or marker_result.rows[0]["compacted_through"] < compacted_through
                ):
                    raise EventStoreError("Could not verify SQLite event compaction")
            after_version, after_prefix = await self._stream_bounds(stream_id)
            if after_version != current_version or after_prefix != max(
                previous_prefix, compacted_through
            ):
                raise EventStoreError("Could not verify SQLite event compaction")
        return result.affected_rows

    async def close(self) -> None:
        """Close the database connection."""
        self._connected = False
        logger.info("SQLite event store disconnected")

    async def __aenter__(self) -> SqliteEventStore:
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
