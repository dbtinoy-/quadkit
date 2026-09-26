"""PostgreSQL Snapshot Store Implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from typing import TYPE_CHECKING, Any

from quadkit.contracts.data.identifiers import Table
from quadkit.events.stores.base import AbstractSnapshotStore
from quadkit.events.stores.postgres.queries import PostgresQueries
from quadkit.events.types import Snapshot
from quadkit.logging import get_logger
from quadkit.serialization import dumps, loads

if TYPE_CHECKING:
    from uuid import UUID

    from quadkit.contracts.data.sql.database import DatabaseProviderProtocol
    from quadkit.events.stores.postgres.config import PostgresEventStoreConfig

logger = get_logger(__name__)


class PostgresSnapshotStore(AbstractSnapshotStore):
    """PostgreSQL snapshot store implementation.

    This store manages aggregate snapshots for optimized loading.
    Standardized to Snapshot objects (M-14).
    """

    def __init__(
        self,
        config: PostgresEventStoreConfig,
        provider: DatabaseProviderProtocol,
    ) -> None:
        """Initialize PostgreSQL snapshot store.

        Args:
            config: PostgreSQL configuration (for table names).
            provider: The generic database provider injected via DI.
        """
        self.config = config
        self.provider = provider
        self._table = str(Table(self.config.snapshots_table))
        self._connected = False

    async def connect(self) -> None:
        """Connection managed by provider."""
        self._connected = True

    async def save_snapshot(self, snapshot: Snapshot) -> None:
        """Save a snapshot (M-14 standardized API)."""
        await self.provider.execute(
            PostgresQueries.INSERT_SNAPSHOT.format(table=self._table),
            [
                snapshot.aggregate_id,
                snapshot.aggregate_type,
                snapshot.version,
                dumps(snapshot.state),
                snapshot.timestamp or datetime.now(UTC),
            ],
        )

    async def get_latest(self, aggregate_id: str) -> Snapshot | None:
        """Get the latest snapshot (M-14 standardized API)."""
        result = await self.provider.execute_query(
            PostgresQueries.GET_LATEST_SNAPSHOT.format(table=self._table),
            [aggregate_id],
        )

        if not result.rows:
            return None

        return self._row_to_snapshot(result.rows[0])

    async def get_by_version(
        self,
        aggregate_id: str | UUID,
        version: int,
    ) -> Snapshot | None:
        """Get a specific snapshot version."""
        result = await self.provider.execute_query(
            PostgresQueries.GET_SNAPSHOT_BY_VERSION.format(table=self._table),
            [str(aggregate_id), version],
        )

        if not result.rows:
            return None

        return self._row_to_snapshot(result.rows[0])

    async def delete(self, aggregate_id: str | UUID) -> None:
        """Delete all snapshots for an aggregate."""
        await self.provider.execute_delete(
            self._table,
            "aggregate_id = $1",
            [str(aggregate_id)],
        )

    async def close(self) -> None:
        """Cleanup resources."""
        self._connected = False

    def _row_to_snapshot(self, row: Any) -> Snapshot:
        """Convert database row to Snapshot object."""
        state = loads(row["state"])
        timestamp = row["timestamp"]

        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        return Snapshot(
            aggregate_id=row["aggregate_id"],
            aggregate_type=row["aggregate_type"],
            version=row["version"],
            state=state,
            timestamp=timestamp,
        )

    async def __aenter__(self) -> PostgresSnapshotStore:
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
