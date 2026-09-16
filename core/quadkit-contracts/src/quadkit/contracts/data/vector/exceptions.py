from __future__ import annotations

from quadkit.contracts.exceptions.infra import InfrastructureError

__all__ = [
    "EmbeddingError",
    "VectorError",
    "VectorIndexError",
    "VectorStoreError",
]


class VectorError(InfrastructureError):
    """Base exception for vector store errors.

    Extends InfrastructureError because vector operations involve
    external network I/O and database connections.
    """

    _code = "QK_ERR_VEC_001"


class VectorStoreError(VectorError):
    """Exception raised during vector store operations (CRUD, search)."""

    _code = "QK_ERR_VEC_002"


class EmbeddingError(VectorError):
    """Exception raised during embedding generation or retrieval."""

    _code = "QK_ERR_VEC_003"


class VectorIndexError(VectorError):
    """Exception raised during vector index creation or management."""

    _code = "QK_ERR_VEC_004"
