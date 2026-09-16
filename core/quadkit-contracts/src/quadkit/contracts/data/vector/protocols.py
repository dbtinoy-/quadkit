"""Vector store protocol definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.core.health import HealthCheckResult
    from quadkit.contracts.data.vector.enums import DistanceMetric
    from quadkit.contracts.data.vector.filters import (
        MetadataCondition,
        MetadataConditionGroup,
    )
    from quadkit.contracts.data.vector.types import (
        CollectionConfig,
        CollectionInfo,
        DeleteResult,
        SearchQuery,
        SearchResult,
        UpsertResult,
        VectorRecord,
    )


@runtime_checkable
class VectorStoreProtocol(Protocol):
    """Top-level vector store lifecycle and collection management.

    Implementations manage connections, collection CRUD, and delegate
    vector operations to ``VectorCollectionProtocol`` instances.
    """

    async def connect(self) -> None:
        """Establish connection to the vector store."""
        ...

    async def disconnect(self) -> None:
        """Close all connections and release resources."""
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check store connectivity and readiness."""
        ...

    async def list_collections(self) -> list[CollectionInfo]:
        """List all collections with metadata."""
        ...

    async def create_collection(self, config: CollectionConfig) -> None:
        """Create a new vector collection.

        Raises:
            CollectionAlreadyExistsError: If collection name is taken.
            VectorConfigError: If config is invalid for this backend.
        """
        ...

    async def delete_collection(self, name: str) -> None:
        """Delete a collection and all its vectors.

        Raises:
            CollectionNotFoundError: If collection does not exist.
        """
        ...

    async def collection_exists(self, name: str) -> bool:
        """Check whether a collection exists."""
        ...

    async def get_collection(self, name: str) -> VectorCollectionProtocol:
        """Get a handle to an existing collection.

        Raises:
            CollectionNotFoundError: If collection does not exist.
        """
        ...

    async def add_texts(
        self,
        texts: list[str],
        embeddings: list[list[float]] | None = None,
        metadatas: list[dict[str, Any]] | None = None,
        collection_name: str | None = None,
    ) -> UpsertResult:
        """Add texts to a collection.

        Convenience method that handles collection routing. If embeddings
        are not provided, the implementation may compute them internally
        or raise an error.
        """
        ...


@runtime_checkable
class VectorCollectionProtocol(Protocol):
    """Vector operations within a single collection.

    All similarity search, upsert, and delete operations operate
    on vectors within a named, dimensioned collection.
    """

    @property
    def name(self) -> str:
        """Collection name."""
        ...

    @property
    def dimension(self) -> int:
        """Vector dimensionality."""
        ...

    @property
    def distance_metric(self) -> DistanceMetric:
        """Distance function used for similarity."""
        ...

    async def upsert(self, records: list[VectorRecord]) -> UpsertResult:
        """Insert or update vectors.

        If a record with the same ID exists, it is replaced.

        Raises:
            DimensionMismatchError: If any vector has wrong dimensionality.
        """
        ...

    async def search(self, query: SearchQuery) -> list[SearchResult]:
        """Find the most similar vectors to the query vector.

        Returns results ordered by similarity (best first),
        limited to ``query.top_k``.

        Raises:
            DimensionMismatchError: If query vector has wrong dimensionality.
        """
        ...

    async def get(self, ids: list[str]) -> list[VectorRecord]:
        """Retrieve vectors by their IDs.

        Returns only records that exist — missing IDs are silently skipped.
        """
        ...

    async def delete(self, ids: list[str]) -> DeleteResult:
        """Delete vectors by their IDs."""
        ...

    async def delete_by_filter(
        self,
        filter: MetadataCondition | MetadataConditionGroup,
    ) -> DeleteResult:
        """Delete all vectors matching a metadata filter."""
        ...

    async def count(self) -> int:
        """Return the number of vectors in this collection."""
        ...

    async def update_metadata(
        self,
        id: str,
        metadata: dict[str, Any],
    ) -> bool:
        """Update metadata for a single vector without re-uploading the vector.

        Returns True if the record existed and was updated.
        """
        ...

    async def add_texts(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
    ) -> UpsertResult:
        """Add texts with pre-computed embeddings.

        This is a convenience method that wraps upsert for common use cases.
        """
        ...


__all__ = [
    "VectorCollectionProtocol",
    "VectorStoreProtocol",
]
