"""PostgreSQL event store implementation."""

from __future__ import annotations

import contextlib
from datetime import datetime
from types import TracebackType
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.data.identifiers import Table
from quadkit.events.exceptions import ConcurrencyError
from quadkit.events.stores.base import AbstractEventStore, StoredEvent
from quadkit.events.stores.postgres.queries import PostgresQueries
from quadkit.logging import get_logger
from quadkit.serialization import dumps, loads

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from quadkit.contracts.data.sql.database import DatabaseProviderProtocol
    from quadkit.events.messages.event import Event
    from quadkit.events.stores.postgres.config import PostgresEventStoreConfig

logger = get_logger(__name__)


class PostgresEventStore(AbstractEventStore):
    """PostgreSQL event store implementation.

    This store uses the generic DatabaseProviderProtocol for async database access.
    Events are stored with optimistic concurrency control.
    """

    def __init__(
        self,
        config: PostgresEventStoreConfig,
        provider: DatabaseProviderProtocol,
        event_serializer: Any | None = None,
    ) -> None:
        """Initialize PostgreSQL event store.

        Args:
            config: PostgreSQL configuration (for table names).
            provider: The generic database provider injected via DI.
            event_serializer: Optional custom event serializer.
        """
        self.config = config
        self.provider = provider
        self.event_serializer = event_serializer
        self._table = str(Table(self.config.events_table))
        self._connected: bool = False

    async def connect(self) -> None:
        """Connection is managed by the provider."""
        self._connected = True
        logger.info("PostgreSQL event store connected via provider")

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
            # Serialize concurrent appends to the same stream. Under the
            # default READ COMMITTED isolation the version check in
            # ``_write_events`` is check-then-insert: two transactions
            # could both observe the same version and both pass the
            # optimistic check, double-appending events. The per-stream
            # advisory lock (held until transaction end) makes the check
            # authoritative; the key is stable across connections.
            await self.provider.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended($1::text, 0))",
                [stream_id],
            )
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
        # Check current version
        res = await self.provider.execute_query(
            PostgresQueries.GET_STREAM_VERSION.format(table=self._table),
            [stream_id],
        )
        current_version = int(res.rows[0]["version"]) if res.rows else 0

        if expected_version is not None and current_version != expected_version:
            raise ConcurrencyError(stream_id, expected_version, current_version or 0)

        for i, event in enumerate(events):
            version = current_version + i + 1
            event_data = self._serialize_event(event)
            event_id = getattr(event, "id", None) or getattr(event, "event_id", None)

            await self.provider.execute(
                PostgresQueries.INSERT_EVENT.format(table=self._table),
                [
                    stream_id,
                    version,
                    str(event_id) if event_id else None,
                    type(event).__name__,
                    dumps(event_data),
                    dumps(getattr(event, "metadata", {})),
                    getattr(event, "timestamp", None),
                ],
            )

        return current_version + len(events)

    async def read(
        self,
        stream_id: str,
        from_version: int = 0,
        to_version: int | None = None,
        limit: int | None = None,
    ) -> list[Event]:
        """Read events from a stream (M-15)."""

        query = PostgresQueries.READ_STREAM.format(table=self._table)
        args: list[Any] = [stream_id, from_version, to_version]

        if limit is not None:
            query += " LIMIT $4"
            args.append(limit)

        result = await self.provider.execute_query(query, args)
        events = list(map(self._deserialize_event, result.rows))

        # M-03: Apply upcasting
        return await self._apply_upcasting(events)

    async def get_stream_ids(self) -> list[str]:
        """Get all stream IDs in the store."""
        result = await self.provider.execute_query(
            f"SELECT DISTINCT stream_id FROM {self._table}"  # noqa: S608 — table name from validated Table() identifier, never user input
        )
        return [row["stream_id"] for row in result.rows]

    async def compact(self, stream_id: str, up_to_version: int) -> int:
        """Purge events for a stream up to (and including) the given version (MF-04)."""
        result = await self.provider.execute_delete(
            self._table,
            "stream_id = $1 AND stream_version <= $2",
            [stream_id, up_to_version],
        )
        return result.affected_rows

    async def get_stream_version(self, stream_id: str) -> int:
        """Get current stream version."""
        result = await self.provider.execute_query(
            PostgresQueries.GET_STREAM_VERSION.format(table=self._table),
            [stream_id],
        )
        return int(result.rows[0]["version"]) if result.rows else 0

    async def stream_all(
        self,
        from_position: int = 0,
        batch_size: int = 100,
        partition: int | None = None,
        total_partitions: int | None = None,
    ) -> AsyncIterator[Event]:
        """Stream all events from a global position."""
        position = from_position

        while True:
            if partition is not None and total_partitions is not None:
                result = await self.provider.execute_query(
                    PostgresQueries.STREAM_ALL_PARTITIONED.format(table=self._table),
                    [position, batch_size, total_partitions, partition],
                )
            else:
                result = await self.provider.execute_query(
                    PostgresQueries.STREAM_ALL.format(table=self._table),
                    [position, batch_size],
                )

            if not result.rows:
                break

            for row in result.rows:
                event = self._deserialize_event(row)
                # M-03: Apply upcasting per event for streaming
                migrated = await self._apply_upcasting([event])
                yield migrated[0]
                position = row["global_sequence"]

    async def get_stored_events_since(
        self,
        global_sequence: int = 0,
        *,
        limit: int = 1000,
    ) -> list[StoredEvent]:
        """Get stored events since a global sequence."""
        result = await self.provider.execute_query(
            PostgresQueries.GET_STORED_SINCE.format(table=self._table),
            [global_sequence, limit],
        )

        return [
            StoredEvent(
                global_sequence=int(row["global_sequence"]),
                stream_id=str(row["stream_id"]),
                stream_version=int(row["stream_version"]),
                event_id=row["event_id"],
                event_type=str(row["event_type"]),
                event_data=loads(row["event_data"]),
                metadata=loads(row["metadata"]) if row["metadata"] else {},
                timestamp=row["timestamp"],
            )
            for row in result.rows
        ]

    async def stream_by_type(
        self,
        event_types: list[str],
        from_position: int = 0,
    ) -> AsyncIterator[Event]:
        """Stream events filtered by type."""
        result = await self.provider.execute_query(
            PostgresQueries.STREAM_BY_TYPE.format(table=self._table),
            [from_position, event_types],
        )

        for row in result.rows:
            event = self._deserialize_event(row)
            # M-03: Apply upcasting
            migrated = await self._apply_upcasting([event])
            yield migrated[0]

    async def find_by_type(
        self,
        event_type: str,
        count: int = 100,
        start: int = 0,
    ) -> list[Event]:
        """Get events of a specific type (paged)."""
        result = await self.provider.execute_query(
            PostgresQueries.GET_BY_TYPE_PAGED.format(table=self._table),
            [event_type, count, start],
        )

        return list(map(self._deserialize_event, result.rows))

    async def get_events_count(self, stream_id: str | None = None) -> int:
        """Get total event count."""
        if stream_id:
            result = await self.provider.execute_query(
                f"SELECT COUNT(*) as count FROM {self._table} WHERE stream_id = $1",  # noqa: S608 — table name from validated Table() identifier, never user input
                [stream_id],
            )
        else:
            result = await self.provider.execute_query(
                f"SELECT COUNT(*) as count FROM {self._table}"  # noqa: S608 — table name from validated Table() identifier, never user input
            )

        return int(result.rows[0]["count"]) if result.rows else 0

    async def delete_stream(self, stream_id: str) -> int:
        """Delete all events for a stream."""
        result = await self.provider.execute_delete(
            self._table, "stream_id = $1", [stream_id]
        )
        return result.affected_rows

    def _serialize_event(self, event: Event) -> dict[str, Any]:
        """Serialize an event to dict."""
        if self.event_serializer:
            return cast("dict[str, Any]", self.event_serializer.serialize(event))
        if hasattr(event, "model_dump"):
            return cast("dict[str, Any]", event.model_dump(mode="json"))
        return dict(getattr(event, "__dict__", {}))

    def _deserialize_event(self, row: Any) -> Event:
        """Deserialize an event from database row."""
        if self.event_serializer:
            from quadkit.events.messages.event import Event as _EventType

            return cast(
                "_EventType",
                self.event_serializer.deserialize(row["event_type"], row["event_data"]),
            )

        event_data = loads(row["event_data"])
        event_id = row.get("event_id")
        try:
            if isinstance(event_id, str):
                event_id = UUID(event_id)
        except (ValueError, TypeError):
            pass

        timestamp = row.get("timestamp")
        if isinstance(timestamp, str):
            with contextlib.suppress(ValueError, TypeError):
                timestamp = datetime.fromisoformat(timestamp)

        occurred_at = event_data.get("occurred_at", timestamp)
        data = {
            **event_data,
            "id": event_id,
            "timestamp": timestamp,
            "occurred_at": occurred_at,
            "version": row.get("stream_version", 0),
            "aggregate_id": row.get("stream_id"),
        }
        from quadkit.events.messages.event import Event as _EventType

        return _EventType(**data)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check health of the event store."""
        try:
            is_conn = await self.provider.is_connected()
            if not is_conn:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    error="Provider not connected",
                    component=self.__class__.__name__,
                )

            await self.provider.execute_query("SELECT 1")
            count_res = await self.provider.execute_query(
                f"SELECT COUNT(*) as count FROM {self._table}"  # noqa: S608 — table name from validated Table() identifier, never user input
            )
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                component=self.__class__.__name__,
                details={
                    "provider": "quadkit-sql",
                    "connected": True,
                    "event_count": int(count_res.rows[0]["count"])
                    if count_res.rows
                    else 0,
                },
            )
        except (
            RuntimeError,
            OSError,
            ConnectionError,
            LookupError,
            AttributeError,
        ) as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                component=self.__class__.__name__,
                error=str(e),
                details={"provider": "quadkit-sql"},
            )

    async def close(self) -> None:
        """Cleanup connection resources."""
        self._connected = False

    async def __aenter__(self) -> PostgresEventStore:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()
