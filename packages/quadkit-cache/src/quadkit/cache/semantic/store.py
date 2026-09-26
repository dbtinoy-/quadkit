"""Three-tier semantic cache store for LLM response caching.

Implements SemanticCacheProtocol with exact hash matching (Tier 1),
vector similarity matching (Tier 2), and cache miss fallback (Tier 3).
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from quadkit.cache.semantic.protocols import VectorIndexProtocol
    from quadkit.contracts.ai.llm import EmbeddingClientProtocol
    from quadkit.contracts.infra.cache.protocols import CacheBackendProtocol

from quadkit.logging import get_logger

logger = get_logger(__name__)


class SemanticCacheStore:
    """Three-tier semantic cache: exact hash → vector similarity → miss.

    Implements SemanticCacheProtocol. Caches LLM responses using a
    three-tier lookup strategy:

    Tier 1 (Exact Hash): Normalizes and hashes the query to look for
      exact matches in the cache backend. Fast, deterministic.

    Tier 2 (Vector Similarity): If Tier 1 misses, embeds the query
      and searches the vector index for similar cached queries. Returns
      the cached response if similarity >= similarity_threshold.

    Tier 3 (Cache Miss): If both tiers miss, returns None for the caller
      to invoke the LLM.

    The store() method populates both Tier 1 and Tier 2. The invalidate()
    method removes from both.
    """

    def __init__(
        self,
        cache_backend: CacheBackendProtocol,
        embedding_client: EmbeddingClientProtocol,
        vector_index: VectorIndexProtocol,
        similarity_threshold: float = 0.95,
        cache_ttl: int | None = None,
    ) -> None:
        """Initialize the semantic cache store.

        Args:
            cache_backend: Backend for exact hash storage (e.g., Redis,
                in-memory cache). Implements CacheBackendProtocol.
            embedding_client: LLM embedding service. Implements
                EmbeddingClientProtocol.
            vector_index: Vector similarity search index. Implements
                VectorIndexProtocol.
            similarity_threshold: Minimum cosine similarity to accept a
                Tier 2 cache hit. Must be in [0, 1]. Defaults to 0.95.
            cache_ttl: Optional TTL in seconds for cache entries.
                Passed to cache_backend.set(). Defaults to None (no expiry).

        Raises:
            ValueError: If similarity_threshold is not in [0, 1].
        """
        if not 0 <= similarity_threshold <= 1:
            raise ValueError(
                f"similarity_threshold must be in [0, 1], got {similarity_threshold}"
            )

        self._cache_backend = cache_backend
        self._embedding_client = embedding_client
        self._vector_index = vector_index
        self._similarity_threshold = similarity_threshold
        self._cache_ttl = cache_ttl

    async def lookup(self, query: str) -> str | None:
        """Look up a query in the cache.

        Checks Tier 1 (exact hash) then Tier 2 (vector similarity).

        Args:
            query: The user query string.

        Returns:
            Cached response string, or None on cache miss.
        """
        # Tier 1: Exact hash match
        hash_key = self._hash_query(query)
        cached_response = cast("str | None", await self._cache_backend.get(hash_key))

        if cached_response is not None:
            logger.debug("semantic_cache_hit_tier1", query_hash=hash_key)
            return cached_response

        # Tier 2: Vector similarity match
        try:
            embeddings = await self._embedding_client.embed([query])
            embedding = embeddings[0]
            results = await self._vector_index.search(embedding, k=1)

            if results:
                similar_hash_key, similarity = results[0]
                if similarity >= self._similarity_threshold:
                    cached_response = cast(
                        "str | None", await self._cache_backend.get(similar_hash_key)
                    )
                    if cached_response is not None:
                        logger.debug(
                            "semantic_cache_hit_tier2",
                            similarity=similarity,
                            threshold=self._similarity_threshold,
                        )
                        return cached_response
                else:
                    logger.debug(
                        "semantic_cache_miss_tier2_below_threshold",
                        similarity=similarity,
                        threshold=self._similarity_threshold,
                    )
            else:
                logger.debug("semantic_cache_miss_tier2_empty_index")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "semantic_cache_tier2_error",
                error=str(exc),
                error_type=type(exc).__name__,
            )

        # Tier 3: Cache miss
        logger.debug("semantic_cache_miss_tier3")
        return None

    async def store(self, query: str, response: str, model: str) -> None:
        """Store a query-response pair in both tiers.

        Stores in Tier 1 (hash key) and Tier 2 (vector index).

        Args:
            query: The user query string.
            response: The LLM response to cache.
            model: The model that produced the response (for logging/tracking).
        """
        hash_key = self._hash_query(query)

        # Tier 1: Store in cache backend
        try:
            await self._cache_backend.set(hash_key, response, ttl=self._cache_ttl)
            logger.debug(
                "semantic_cache_stored_tier1", query_hash=hash_key, model=model
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "semantic_cache_store_tier1_error",
                error=str(exc),
                error_type=type(exc).__name__,
            )

        # Tier 2: Embed and store in vector index
        try:
            embeddings = await self._embedding_client.embed([query])
            embedding = embeddings[0]
            await self._vector_index.add(hash_key, embedding)
            logger.debug(
                "semantic_cache_stored_tier2",
                query_hash=hash_key,
                model=model,
                index_size=self._vector_index.size,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "semantic_cache_store_tier2_error",
                error=str(exc),
                error_type=type(exc).__name__,
            )

    async def invalidate(self, query: str) -> bool:
        """Invalidate a cached entry by query.

        Removes from both Tier 1 (cache backend) and Tier 2 (vector index).

        Args:
            query: The user query string to invalidate.

        Returns:
            True if the entry was found and removed, False otherwise.
        """
        hash_key = self._hash_query(query)
        tier1_result = await self._cache_backend.delete(hash_key)
        tier1_deleted = bool(tier1_result)
        tier2_deleted = await self._vector_index.remove(hash_key)
        deleted = tier1_deleted or tier2_deleted

        if deleted:
            logger.debug("semantic_cache_invalidated", query_hash=hash_key)
        else:
            logger.debug("semantic_cache_invalidate_not_found", query_hash=hash_key)

        return deleted

    @staticmethod
    def _normalize_query(query: str) -> str:
        """Normalize query by lowercasing and stripping whitespace.

        Args:
            query: The user query string.

        Returns:
            Normalized query string.
        """
        return query.lower().strip()

    @staticmethod
    def _hash_query(query: str) -> str:
        """Compute SHA256 hash of normalized query.

        Normalization: lowercase + strip whitespace for consistent hashing.

        Args:
            query: The user query string.

        Returns:
            SHA256 hex digest of the normalized query.
        """
        normalized = SemanticCacheStore._normalize_query(query)
        return hashlib.sha256(normalized.encode()).hexdigest()
