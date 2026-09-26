"""FAISS-backed vector index for semantic cache.

Provides an in-memory vector similarity search backend using Facebook AI
Similarity Search (FAISS). Suitable for single-server deployments with up
to ~1M embeddings. Uses IndexFlatIP with L2-normalized vectors for
cosine similarity computation.
"""

from __future__ import annotations

from quadkit.logging import get_logger

logger = get_logger(__name__)


class FaissVectorIndex:
    """FAISS-backed in-memory vector index for semantic cache.

    Uses IndexFlatIP (inner product on L2-normalized vectors = cosine
    similarity). Suitable for single-server deployments with up to ~1M
    entries. Implements VectorIndexProtocol.

    All vectors must be L2-normalized (unit length) before storage.
    """

    def __init__(self, embedding_dim: int = 384, max_entries: int = 100_000) -> None:
        """Initialize the FAISS vector index.

        Args:
            embedding_dim: Dimension of embedding vectors. Defaults to 384
                (common for sentence-transformers like all-MiniLM-L6-v2).
            max_entries: Maximum number of entries before warning. Defaults to 100,000.

        Raises:
            ImportError: If faiss package is not installed.
            ValueError: If embedding_dim <= 0 or max_entries <= 0.
        """
        if embedding_dim <= 0:
            raise ValueError(f"embedding_dim must be positive, got {embedding_dim}")
        if max_entries <= 0:
            raise ValueError(f"max_entries must be positive, got {max_entries}")

        try:
            import faiss  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "faiss not installed. Install with: pip install faiss-cpu"
            ) from exc

        import faiss

        self._faiss = faiss
        self._index = faiss.IndexFlatIP(embedding_dim)
        self._keys: list[str | None] = []  # FAISS position → cache key
        self._key_to_idx: dict[str, int] = {}
        self._max_entries = max_entries
        self._embedding_dim = embedding_dim

    async def search(
        self, embedding: list[float], k: int = 1
    ) -> list[tuple[str, float]]:
        """Search for the top-k most similar embeddings.

        Args:
            embedding: Query embedding vector (must be L2-normalized).
            k: Number of results to return.

        Returns:
            List of (cache_key, similarity_score) tuples, sorted by
            similarity_score descending. Empty list if index is empty.
        """
        import numpy as np

        if not self._keys or not any(self._keys):
            return []

        # Over-fetch to account for soft-deleted entries that FAISS doesn't know about
        valid_count = sum(1 for key in self._keys if key is not None)
        if valid_count == 0:
            return []

        deleted_count = len(self._keys) - valid_count
        k_adj = min(k + deleted_count, len(self._keys))

        # Convert to numpy array and reshape for FAISS
        query_array = np.array([embedding], dtype=np.float32)

        # Search
        distances, indices = self._index.search(query_array, k_adj)
        distances = distances[0]  # Extract first (only) row
        indices = indices[0]

        results = []
        for idx, distance in zip(indices, distances, strict=False):
            if idx >= 0 and idx < len(self._keys):
                key = self._keys[idx]
                if key is not None:
                    # distance is inner product = cosine similarity for normalized
                    results.append((key, float(distance)))
            if len(results) >= k:  # Stop once we have enough valid results
                break

        return results

    async def add(self, key: str, embedding: list[float]) -> None:
        """Add an embedding to the index.

        If the key already exists, it is not duplicated (early return).
        If the index reaches max_entries, a warning is logged but the
        entry is still added (LRU eviction can be a future enhancement).

        Args:
            key: Cache key identifier for the embedding.
            embedding: Embedding vector (must be L2-normalized).
        """
        import numpy as np

        # Skip if key already exists
        if key in self._key_to_idx:
            return

        # Warn if at capacity
        if len(self._keys) >= self._max_entries:
            logger.warning(
                "semantic_cache_index_at_capacity",
                size=len(self._keys),
                max_entries=self._max_entries,
            )

        # Add to FAISS index
        vector_array = np.array([embedding], dtype=np.float32)
        self._index.add(vector_array)

        # Track the key
        idx = len(self._keys)
        self._keys.append(key)
        self._key_to_idx[key] = idx

    async def remove(self, key: str) -> bool:
        """Remove an entry from the index by cache key.

        FAISS IndexFlatIP does not support deletion. We use a soft-delete
        approach by marking the slot with None. Removed entries are skipped
        in search results.

        Args:
            key: Cache key identifier to remove.

        Returns:
            True if the key was found and removed, False if not found.
        """
        if key not in self._key_to_idx:
            return False

        idx = self._key_to_idx[key]
        if idx < len(self._keys) and self._keys[idx] is not None:
            self._keys[idx] = None
            del self._key_to_idx[key]
            return True

        return False

    @property
    def size(self) -> int:
        """Number of entries currently indexed (excluding deleted entries).

        Returns:
            Non-negative integer.
        """
        return sum(1 for key in self._keys if key is not None)
