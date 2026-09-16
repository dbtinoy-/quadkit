"""NoSQL database protocols for document-oriented storage.

Provides driver-agnostic abstractions for document stores (MongoDB,
DynamoDB, CouchDB, etc.) parallel to the SQL-centric
``DatabaseProviderProtocol``.

Key protocols:

- :class:`CollectionProtocol` — CRUD, indexing, and aggregation on a
  single collection / table.
- :class:`DocumentStoreProtocol` — connection lifecycle, collection
  access, and health checks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from contextlib import AbstractAsyncContextManager

    from quadkit.contracts.core.health import HealthCheckResult


# ============================================================
# Result types
# ============================================================


@dataclass(frozen=True, slots=True)
class DocumentResult:
    """Result of a single document operation."""

    document_id: str | None = None
    matched_count: int = 0
    modified_count: int = 0
    upserted_id: str | None = None
    acknowledged: bool = True


@dataclass(frozen=True, slots=True)
class BulkWriteResult:
    """Result of a bulk write operation."""

    inserted_count: int = 0
    matched_count: int = 0
    modified_count: int = 0
    deleted_count: int = 0
    upserted_ids: list[str] = field(default_factory=list)


# ============================================================
# Collection protocol
# ============================================================


@runtime_checkable
class CollectionProtocol(Protocol):
    """Protocol for a NoSQL collection / table abstraction.

    Provides document-oriented CRUD operations without SQL
    assumptions.  Maps to MongoDB collections, DynamoDB tables, etc.
    """

    @property
    def name(self) -> str:
        """Collection / table name."""
        ...

    async def insert_one(self, document: dict[str, Any]) -> DocumentResult:
        """Insert a single document."""
        ...

    async def insert_many(self, documents: list[dict[str, Any]]) -> BulkWriteResult:
        """Insert multiple documents."""
        ...

    async def find_one(
        self,
        filter: dict[str, Any],
        *,
        projection: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Find a single document matching the filter."""
        ...

    async def find(
        self,
        filter: dict[str, Any],
        *,
        projection: dict[str, Any] | None = None,
        sort: list[tuple[str, int]] | None = None,
        skip: int = 0,
        limit: int = 0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Find documents matching the filter. Returns async iterator."""
        ...

    async def update_one(
        self,
        filter: dict[str, Any],
        update: dict[str, Any],
        *,
        upsert: bool = False,
    ) -> DocumentResult:
        """Update a single document matching the filter."""
        ...

    async def update_many(
        self,
        filter: dict[str, Any],
        update: dict[str, Any],
    ) -> DocumentResult:
        """Update all documents matching the filter."""
        ...

    async def delete_one(self, filter: dict[str, Any]) -> DocumentResult:
        """Delete a single document matching the filter."""
        ...

    async def delete_many(self, filter: dict[str, Any]) -> DocumentResult:
        """Delete all documents matching the filter."""
        ...

    async def replace_one(
        self,
        filter: dict[str, Any],
        replacement: dict[str, Any],
        *,
        upsert: bool = False,
    ) -> DocumentResult:
        """Replace a single document matching the filter."""
        ...

    async def find_one_and_update(
        self,
        filter: dict[str, Any],
        update: dict[str, Any],
        *,
        upsert: bool = False,
        return_document: bool = True,
    ) -> dict[str, Any] | None:
        """Atomically find and update a document.

        Args:
            filter: Match criteria.
            update: Update operations.
            upsert: Insert if no match.
            return_document: If True, return the updated document.

        Returns:
            The document (before or after update) or None.
        """
        ...

    async def count_documents(self, filter: dict[str, Any] | None = None) -> int:
        """Count documents matching the filter."""
        ...

    async def create_index(
        self,
        keys: list[tuple[str, int]],
        *,
        unique: bool = False,
        name: str | None = None,
    ) -> str:
        """Create an index on the collection. Returns the index name."""
        ...

    async def aggregate(
        self,
        pipeline: list[dict[str, Any]],
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute an aggregation pipeline."""
        ...

    async def list_indexes(self) -> list[dict[str, Any]]:
        """List all indexes on the collection."""
        ...

    async def distinct(
        self,
        key: str,
        filter: dict[str, Any] | None = None,
    ) -> list[Any]:
        """Get distinct values for a specified key."""
        ...

    async def bulk_write(self, operations: list[Any]) -> BulkWriteResult:
        """Execute multiple write operations in a single batch.

        Operations are driver-specific write models (e.g., UpdateOne, InsertOne).
        """
        ...


# ============================================================
# Document store protocol
# ============================================================


@runtime_checkable
class DocumentStoreProtocol(Protocol):
    """Protocol for a document-oriented database provider.

    Parallel to ``DatabaseProviderProtocol`` but without SQL
    assumptions.  Provides collection access, session management,
    and health checks.
    """

    async def connect(self) -> None:
        """Establish connection to the document store."""
        ...

    async def disconnect(self) -> None:
        """Close all connections."""
        ...

    def is_connected(self) -> bool:
        """Check if the store is connected."""
        ...

    def collection(self, name: str) -> CollectionProtocol:
        """Get a collection / table handle by name."""
        ...

    def session(self) -> AbstractAsyncContextManager[Any]:
        """Create a session for multi-document transactions."""
        ...

    async def list_collections(self) -> list[str]:
        """List all collection names in the database."""
        ...

    async def drop_collection(self, name: str) -> None:
        """Drop a collection."""
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check document store connectivity and health."""
        ...


__all__ = [
    "BulkWriteResult",
    "CollectionProtocol",
    "DocumentResult",
    "DocumentStoreProtocol",
]
