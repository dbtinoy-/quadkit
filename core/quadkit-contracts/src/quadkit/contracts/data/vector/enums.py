"""Vector store enumerations."""

from __future__ import annotations

from enum import StrEnum


class DistanceMetric(StrEnum):
    """Distance function used for similarity search."""

    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    DOT_PRODUCT = "dot_product"
    MANHATTAN = "manhattan"


class IndexType(StrEnum):
    """Vector index algorithm."""

    FLAT = "flat"
    HNSW = "hnsw"
    IVFFLAT = "ivfflat"
    ANNOY = "annoy"


class IndexState(StrEnum):
    """Current state of a vector index/collection."""

    CREATING = "creating"
    READY = "ready"
    UPDATING = "updating"
    ERROR = "error"
    DELETING = "deleting"


__all__ = [
    "DistanceMetric",
    "IndexState",
    "IndexType",
]
