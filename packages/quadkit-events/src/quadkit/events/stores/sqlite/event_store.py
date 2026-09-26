"""SQLite event store implementation.

This module provides the SqliteEventStore class for event sourcing
with SQLite backend using the generic database provider.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from typing import TYPE_CHECKING, Any

from quadkit.contracts.data.identifiers import Table
from quadkit.events.config import SqliteConfig
from quadkit.events.exceptions import ConcurrencyError
from quadkit.events.stores.base import AbstractEventStore
from quadkit.events.stores.sqlite.queries import SqliteQueries
from quadkit.events.stores.sqlite.serializer import SqliteEventSerializer
from quadkit.logging import get_logger
from quadkit.serialization import dumps

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from quadkit.contracts.data.sql.database import DatabaseProviderProtocol
    from quadkit.events.messages.event import Event

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
        if self.config.auto_create_tables:
            await self._create_tables()

        self._connected = True
        logger.info("SQLite event store connected via provider")

    async def _create_tables(self) -> None:
        """Create events table if it doesn't exist."""
        ddl = self.queries.get_create_events_table_sql()

        for statement in ddl.split(";"):
            if statement.strip():
                await self.provider.execute_query(statement)

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
                metadata = getattr(event, "metadata", {})
                if hasattr(metadata, "model_dump"):
                    metadata = metadata.model_dump(mode="json")

                await self.provider.execute(
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

        result = await self.provider.execute_query(query, args)
        events = [self.serializer.deserialize_event(row) for row in result.rows]

        # M-03: Apply upcasting
        return await self._apply_upcasting(events)

    async def get_stream_version(self, stream_id: str) -> int:
        """Get current stream version."""
        result = await self.provider.execute_query(
            self.queries.get_stream_version_sql(),
            [stream_id],
        )

        return (
            int(
                result.rows[0]["version"]
                if "version" in result.rows[0]
                else next(iter(result.rows[0].values()))
            )
            if result.rows
            else 0
        )

    async def stream_all(
        self,
        from_position: int = 0,
        batch_size: int = 100,
        partition: int | None = None,
        total_partitions: int | None = None,
    ) -> AsyncIterator[Event]:
        """Stream all events from a global position."""
        position = from_position

        if not self._connected:
            await self.connect()

        while True:
            if partition is not None and total_partitions is not None:
                result = await self.provider.execute_query(
                    self.queries.get_stream_all_partitioned_sql(),
                    [position, total_partitions, partition, batch_size],
                )
            else:
                result = await self.provider.execute_query(
                    self.queries.get_stream_all_sql(),
                    [position, batch_size],
                )

            if not result.rows:
                break

            for row in result.rows:
                event = self.serializer.deserialize_event(row)
                migrated = await self._apply_upcasting([event])
                yield migrated[0]
                position = row["global_sequence"]

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

        for row in result.rows:
            event = self.serializer.deserialize_event(row)
            migrated = await self._apply_upcasting([event])
            yield migrated[0]

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

        return [self.serializer.deserialize_event(row) for row in result.rows]

    async def get_events_count(self, stream_id: str | None = None) -> int:
        """Get total event count."""
        query = self.queries.get_events_count_sql(stream_id)
        if stream_id:
            result = await self.provider.execute_query(query, [stream_id])
        else:
            result = await self.provider.execute_query(query)

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
        count = await self.get_events_count(stream_id)
        await self.provider.execute(
            self.queries.get_delete_stream_sql(),
            [stream_id],
        )
        return count

    async def get_stream_ids(self) -> list[str]:
        """Get all stream IDs in the store."""
        if not self._connected:
            await self.connect()

        result = await self.provider.execute_query(
            self.queries.get_all_stream_ids_sql()
        )
        return [
            row["stream_id"] if "stream_id" in row else next(iter(row.values()))
            for row in result.rows
        ]

    async def compact(self, stream_id: str, up_to_version: int) -> int:
        """Purge events for a stream up to (and including) the given version (MF-04)."""
        if not self._connected:
            await self.connect()

        result = await self.provider.execute_delete(
            str(Table(self.config.events_table)),
            "stream_id = ? AND stream_version <= ?",
            [stream_id, up_to_version],
        )
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
