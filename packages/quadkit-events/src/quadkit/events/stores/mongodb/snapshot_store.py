"""
MongoDB snapshot store implementation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import TracebackType
from typing import TYPE_CHECKING, Any

from quadkit.events.stores.base import AbstractSnapshotStore
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from uuid import UUID

    from motor.motor_asyncio import (
        AsyncIOMotorClient,
        AsyncIOMotorCollection,
        AsyncIOMotorDatabase,
    )

    from quadkit.events.stores.mongodb.config import MongoDBConfig
    from quadkit.events.types import Snapshot


logger = get_logger(__name__)


class MongoDBSnapshotStore(AbstractSnapshotStore):
    """MongoDB snapshot store implementation.

    This store manages aggregate snapshots for optimized loading.

    Example:
        ```python
        config = MongoDBConfig(uri="mongodb://localhost:27017")
        store = MongoDBSnapshotStore(config)
        await store.connect()

        # Save snapshot
        await store.save(Snapshot(
            aggregate_id="order-123",
            aggregate_type="Order",
            version=100,
            state=order.to_dict(),
        ))

        # Load latest
        snapshot = await store.get_latest("order-123")
        ```
    """

    def __init__(self, config: MongoDBConfig) -> None:
        """Initialize MongoDB snapshot store.

        Args:
            config: MongoDB configuration.
        """
        self.config = config
        self._client: AsyncIOMotorClient | None = None
        self._db: AsyncIOMotorDatabase | None = None
        self._snapshots: AsyncIOMotorCollection | None = None
        self._connected = False

    @property
    def snapshots(self) -> AsyncIOMotorCollection:
        if self._snapshots is None:
            raise RuntimeError("MongoDBSnapshotStore is not connected")
        return self._snapshots

    async def connect(self) -> None:
        """Connect to MongoDB."""
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
        except ImportError as e:
            raise ImportError(
                "motor is required for MongoDBSnapshotStore. "
                "Install with: pip install motor",
            ) from e

        self._client = AsyncIOMotorClient(
            self.config.uri.get_secret_value(),
            maxPoolSize=self.config.max_pool_size,
        )
        self._db = self._client[self.config.database]
        self._snapshots = self._db[self.config.snapshots_collection]

        if self.config.auto_create_indexes:
            await self._create_indexes()

        self._connected = True

    async def _create_indexes(self) -> None:
        """Create indexes for efficient querying."""
        await self.snapshots.create_index(
            [("aggregate_id", 1), ("version", 1)],
            unique=True,
        )
        await self.snapshots.create_index([("aggregate_id", 1)])

    async def save_snapshot(self, snapshot: Snapshot) -> None:
        """Save a snapshot (M-14 standardized API)."""
        doc = {
            "aggregate_id": snapshot.aggregate_id,
            "aggregate_type": snapshot.aggregate_type,
            "version": snapshot.version,
            "state": snapshot.state,
            "timestamp": snapshot.timestamp or datetime.now(UTC),
        }

        await self.snapshots.update_one(
            {
                "aggregate_id": snapshot.aggregate_id,
                "version": snapshot.version,
            },
            {"$set": doc},
            upsert=True,
        )

    async def get_latest(self, aggregate_id: str) -> Snapshot | None:
        """Get latest snapshot (M-14 standardized API)."""
        doc = await self.snapshots.find_one(
            {"aggregate_id": aggregate_id},
            sort=[("version", -1)],
        )

        if doc is None:
            return None

        return self._doc_to_snapshot(doc)

    async def get_by_version(
        self,
        aggregate_id: str | UUID,
        version: int,
    ) -> Snapshot | None:
        """Get a specific snapshot version (M-14)."""
        doc = await self.snapshots.find_one(
            {
                "aggregate_id": str(aggregate_id),
                "version": version,
            },
        )

        if doc is None:
            return None

        return self._doc_to_snapshot(doc)

    def _doc_to_payload(self, doc: dict[str, Any]) -> tuple[Any, int]:
        """Convert a MongoDB document to payload."""
        payload = {
            "state": doc["state"],
            "timestamp": doc.get("timestamp") or datetime.now(UTC),
            "aggregate_type": doc.get("aggregate_type", "Unknown"),
        }
        return payload, doc["version"]

    async def delete_old_snapshots(
        self,
        aggregate_id: str | UUID,
        keep_count: int = 3,
    ) -> int:
        """Delete old snapshots, keeping only the most recent ones.

        Args:
            aggregate_id: Aggregate identifier.
            keep_count: Number of snapshots to keep.

        Returns:
            Number of deleted snapshots.
        """
        # Get versions to keep
        cursor = (
            self.snapshots.find(
                {"aggregate_id": str(aggregate_id)},
                projection={"version": 1},
            )
            .sort("version", -1)
            .limit(keep_count)
        )

        versions_to_keep = []
        async for doc in cursor:
            versions_to_keep.append(doc["version"])

        # Delete the rest
        result = await self.snapshots.delete_many(
            {
                "aggregate_id": str(aggregate_id),
                "version": {"$nin": versions_to_keep},
            },
        )

        return int(result.deleted_count)

    def _doc_to_snapshot(self, doc: dict[str, Any]) -> Snapshot:
        """Convert a MongoDB document to a Snapshot (M-14)."""
        from quadkit.events.types import Snapshot

        return Snapshot(
            aggregate_id=doc["aggregate_id"],
            aggregate_type=doc["aggregate_type"],
            version=doc["version"],
            state=doc["state"],
            timestamp=doc.get("timestamp") or datetime.now(UTC),
        )

    async def close(self) -> None:
        """Close the MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            self._snapshots = None
            self._connected = False

    async def __aenter__(self) -> MongoDBSnapshotStore:
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
