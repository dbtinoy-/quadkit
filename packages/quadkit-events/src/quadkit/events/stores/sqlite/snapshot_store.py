"""SQLite snapshot store implementation.

This module provides the SqliteSnapshotStore class for managing
aggregate snapshots using the generic database provider.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from typing import TYPE_CHECKING, Any

from quadkit.contracts.data.identifiers import Table
from quadkit.events.config import SqliteConfig
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
        if self.config.auto_create_tables:
            await self._create_table()

        self._connected = True

    async def _create_table(self) -> None:
        """Create snapshots table if it doesn't exist."""
        ddl = self.queries.get_create_snapshots_table_sql()

        for statement in ddl.split(";"):
            if statement.strip():
                await self.provider.execute_query(statement)

    async def save_snapshot(self, snapshot: Snapshot) -> None:
        """Save a snapshot (M-14 standardized API)."""
        await self.provider.execute_insert(
            str(Table(self.config.snapshots_table)),
            {
                "aggregate_id": snapshot.aggregate_id,
                "aggregate_type": snapshot.aggregate_type,
                "version": snapshot.version,
                "state": dumps(snapshot.state).decode("utf-8")
                if isinstance(dumps(snapshot.state), bytes)
                else dumps(snapshot.state),
                "timestamp": (snapshot.timestamp or datetime.now(UTC)).isoformat(),
            },
        )

    async def get_latest(self, aggregate_id: str) -> Snapshot | None:
        """Get latest snapshot (M-14 standardized API)."""
        result = await self.provider.execute_query(
            self.queries.get_load_snapshot_sql(),
            [str(aggregate_id)],
        )

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

        if not result.rows:
            return None

        return self._row_to_snapshot(result.rows[0])

    async def delete_old_snapshots(
        self,
        aggregate_id: str | UUID,
        keep_count: int = 3,
    ) -> int:
        """Delete old snapshots, keeping only the most recent ones."""
        async with self.provider.transaction():
            # Get count before delete
            count_res = await self.provider.execute_query(
                self.queries.get_snapshot_count_sql(),
                [str(aggregate_id)],
            )
            total = (
                int(
                    count_res.rows[0]["count"]
                    if "count" in count_res.rows[0]
                    else next(iter(count_res.rows[0].values()))
                )
                if count_res.rows
                else 0
            )

            # Delete old snapshots
            await self.provider.execute(
                self.queries.get_delete_old_snapshots_sql(),
                [str(aggregate_id), str(aggregate_id), keep_count],
            )

            # Calculate deleted count (after commit for accuracy)
            remaining_res = await self.provider.execute_query(
                self.queries.get_snapshot_count_sql(),
                [str(aggregate_id)],
            )
            remaining = (
                int(
                    remaining_res.rows[0]["count"]
                    if "count" in remaining_res.rows[0]
                    else next(iter(remaining_res.rows[0].values()))
                )
                if remaining_res.rows
                else 0
            )

            return total - remaining

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
