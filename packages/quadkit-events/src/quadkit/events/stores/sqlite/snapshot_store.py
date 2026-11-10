"""SQLite snapshot store implementation.

This module provides the SqliteSnapshotStore class for managing
aggregate snapshots using the generic database provider.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from typing import TYPE_CHECKING, Any

from quadkit.events.config import SqliteConfig
from quadkit.events.exceptions import EventStoreError
from quadkit.events.stores.base import AbstractSnapshotStore
from quadkit.events.stores.sqlite.queries import SqliteQueries
from quadkit.logging import get_logger
from quadkit.serialization import dumps, loads

if TYPE_CHECKING:
    from uuid import UUID

    from quadkit.contracts.data.sql.database import DatabaseProviderProtocol
    from quadkit.events.types import Snapshot

logger = get_logger(__name__)


class SqliteSnapshotStore(AbstractSnapshotStore):
    """SQLite snapshot store implementation.

    This store manages aggregate snapshots using a generic DatabaseProviderProtocol.
    """

    def __init__(
        self,
        config: SqliteConfig | None = None,
        provider: DatabaseProviderProtocol | None = None,
    ) -> None:
        """Initialize SQLite snapshot store.

        Args:
            config: SQLite configuration.
            provider: The generic database provider injected via DI.
        """
        self.config = config or SqliteConfig()
        if provider is None:
            raise ValueError("provider (DatabaseProviderProtocol) is required")
        self.provider = provider
        self.queries = SqliteQueries(self.config)
        self._connected = False

    async def connect(self) -> None:
        """Connection is managed by the provider."""
        self._connected = False
        if self.config.auto_create_tables:
            await self._create_table()

        self._connected = True

    async def _create_table(self) -> None:
        """Create snapshots table if it doesn't exist."""
        ddl = self.queries.get_create_snapshots_table_sql()

        for statement in ddl.split(";"):
            if statement.strip():
                result = await self.provider.execute_query(statement)
                if not result.success:
                    raise EventStoreError("Could not create SQLite snapshot schema")

    async def save_snapshot(self, snapshot: Snapshot) -> None:
        """Save a snapshot (M-14 standardized API)."""
        if snapshot.metadata:
            raise EventStoreError("SQLite snapshot metadata is not supported")
        state = dumps(snapshot.state)
        async with self.provider.transaction():
            result = await self.provider.execute_insert(
                self.config.snapshots_table,
                {
                    "aggregate_id": str(snapshot.aggregate_id),
                    "aggregate_type": snapshot.aggregate_type,
                    "version": snapshot.version,
                    "state": state.decode("utf-8")
                    if isinstance(state, bytes)
                    else state,
                    "timestamp": (snapshot.timestamp or datetime.now(UTC)).isoformat(),
                },
            )
            if (
                not result.success
                or type(result.affected_rows) is not int
                or result.affected_rows != 1
            ):
                raise EventStoreError("Could not save SQLite snapshot")

    async def get_latest(self, aggregate_id: str) -> Snapshot | None:
        """Get latest snapshot (M-14 standardized API)."""
        result = await self.provider.execute_query(
            self.queries.get_load_snapshot_sql(),
            [str(aggregate_id)],
        )

        if not result.success:
            raise EventStoreError("Could not read SQLite snapshot")
        if not result.rows:
            return None

        return self._row_to_snapshot(result.rows[0])

    def _row_to_snapshot(self, row: dict[str, Any]) -> Snapshot:
        """Convert row to Snapshot (M-14)."""
        from quadkit.events.types import Snapshot

        state_str = row["state"]
        if isinstance(state_str, bytes):
            state_str = state_str.decode("utf-8")

        state = loads(state_str)
        timestamp = row["timestamp"]

        if isinstance(timestamp, str):
            from contextlib import suppress

            with suppress(ValueError):
                timestamp = datetime.fromisoformat(timestamp)

        return Snapshot(
            aggregate_id=row["aggregate_id"],
            aggregate_type=row["aggregate_type"],
            version=row["version"],
            state=state,
            timestamp=timestamp,
        )

    async def get_by_version(
        self,
        aggregate_id: str | UUID,
        version: int,
    ) -> Snapshot | None:
        """Get a specific snapshot version (M-14)."""
        result = await self.provider.execute_query(
            self.queries.get_snapshot_by_version_sql(),
            [str(aggregate_id), version],
        )

        if not result.success:
            raise EventStoreError("Could not read SQLite snapshot")
        if not result.rows:
            return None

        return self._row_to_snapshot(result.rows[0])

    async def delete_old_snapshots(
        self,
        aggregate_id: str | UUID,
        keep_count: int = 3,
    ) -> int:
        """Delete old snapshots, keeping only the most recent ones."""
        if type(keep_count) is not int or keep_count < 0:
            raise ValueError("keep_count must be a non-negative integer")
        async with self.provider.transaction():
            total = await self._snapshot_count(aggregate_id)
            result = await self.provider.execute(
                self.queries.get_delete_old_snapshots_sql(),
                [str(aggregate_id), str(aggregate_id), keep_count],
            )
            if not result.success:
                raise EventStoreError("Could not delete SQLite snapshots")
            remaining = await self._snapshot_count(aggregate_id)
            if remaining != min(total, keep_count):
                raise EventStoreError("Could not verify SQLite snapshot cleanup")
            return total - remaining

    async def _snapshot_count(self, aggregate_id: str | UUID) -> int:
        result = await self.provider.execute_query(
            self.queries.get_snapshot_count_sql(), [str(aggregate_id)]
        )
        if not result.success or len(result.rows) != 1 or len(result.rows[0]) != 1:
            raise EventStoreError("Could not count SQLite snapshots")
        count = next(iter(result.rows[0].values()))
        if type(count) is not int or count < 0:
            raise EventStoreError("Could not count SQLite snapshots")
        return count

    async def close(self) -> None:
        """Close the database connection."""
        self._connected = False

    async def __aenter__(self) -> SqliteSnapshotStore:
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
