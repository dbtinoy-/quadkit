"""Internal protocols for semantic cache vector indexing.

This module defines VectorIndexProtocol which is package-internal to
quadkit-cache. It is not exported to quadkit-contracts because vector
indexing is an implementation detail of SemanticCacheStore, not a public
service boundary for other extensions.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class VectorIndexProtocol(Protocol):
    """Internal protocol for vector similarity search backends.

    Package-internal to quadkit-cache. Not in contracts because it is only
    consumed by SemanticCacheStore within this package. Implementations
    include FaissVectorIndex (in-memory) or adapters to external vector stores.

    Vectors must be normalized to unit length (L2 norm = 1) before storage
    to enable cosine similarity via inner product distance.
    """

    async def search(
        self, embedding: list[float], k: int = 1
    ) -> list[tuple[str, float]]:
        """Search for the top-k most similar embeddings.

        Args:
            embedding: Query embedding vector (must be normalized).
            k: Number of results to return. Defaults to 1.

        Returns:
            List of (cache_key, similarity_score) tuples, sorted by
            similarity_score descending. Empty list if index is empty or
            has no matches. Scores are in range [0, 1].
        """
        ...

    async def add(self, key: str, embedding: list[float]) -> None:
        """Add an embedding to the index.

        Args:
            key: Cache key identifier for the embedding.
            embedding: Embedding vector (must be normalized).
        """
        ...

    async def remove(self, key: str) -> bool:
        """Remove an entry from the index by cache key.

        Args:
            key: Cache key identifier to remove.

        Returns:
            True if the key was found and removed, False if not found.
        """
        ...

    @property
    def size(self) -> int:
        """Number of entries currently indexed.

        Returns:
            Non-negative integer.
        """
        ...
