"""Vector store value types — all immutable, no implementation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from quadkit.contracts.data.vector.enums import (
    DistanceMetric,
    IndexState,
    IndexType,
)

if TYPE_CHECKING:
    from quadkit.contracts.data.vector.filters import MetadataFilter


@dataclass(frozen=True, slots=True)
class VectorRecord:
    """A stored vector with optional metadata and content."""

    id: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)
    content: str | None = None


@dataclass(frozen=True, slots=True)
class SearchQuery:
    """Parameters for a similarity search."""

    vector: list[float]
    top_k: int = 10
    filter: MetadataFilter | None = None
    include_vectors: bool = False
    include_metadata: bool = True
    min_score: float | None = None


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A single similarity search result."""

    id: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    vector: list[float] | None = None
    content: str | None = None


@dataclass(frozen=True, slots=True)
class CollectionConfig:
    """Configuration for creating a new vector collection."""

    name: str
    dimension: int
    distance_metric: DistanceMetric = DistanceMetric.COSINE
    index_type: IndexType = IndexType.HNSW
    hnsw_m: int = 16
    hnsw_ef_construction: int = 200
    metadata_schema: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class CollectionInfo:
    """Metadata about an existing collection."""

    name: str
    dimension: int
    distance_metric: DistanceMetric
    index_type: IndexType
    vector_count: int
    state: IndexState


@dataclass(frozen=True, slots=True)
class UpsertResult:
    """Result of a vector upsert operation."""

    upserted_count: int


@dataclass(frozen=True, slots=True)
class DeleteResult:
    """Result of a vector delete operation."""

    deleted_count: int


__all__ = [
    "CollectionConfig",
    "CollectionInfo",
    "DeleteResult",
    "SearchQuery",
    "SearchResult",
    "UpsertResult",
    "VectorRecord",
]
