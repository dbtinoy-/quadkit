"""SemanticCacheStore three-tier lookup tests."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.cache.semantic.store import SemanticCacheStore


class TestSemanticCacheLookup:
    """Test suite for SemanticCacheStore lookup tiers."""

    @pytest.fixture
    def mock_cache_backend(self) -> MagicMock:
        cache = MagicMock()
        cache.get = AsyncMock(return_value=None)
        cache.set = AsyncMock(return_value=True)
        cache.delete = AsyncMock(return_value=False)
        cache.exists = AsyncMock(return_value=False)
        return cache

    @pytest.fixture
    def mock_embedding_client(self) -> MagicMock:
        client = MagicMock()
        client.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3, 0.4]])
        return client

    @pytest.fixture
    def mock_vector_index(self) -> MagicMock:
        index = MagicMock()
        index.search = AsyncMock(return_value=[])
        index.add = AsyncMock()
        index.remove = AsyncMock(return_value=False)
        index.size = 0
        return index

    @pytest.fixture
    def semantic_cache(
        self,
        mock_cache_backend: MagicMock,
        mock_embedding_client: MagicMock,
        mock_vector_index: MagicMock,
    ) -> SemanticCacheStore:
        return SemanticCacheStore(
            cache_backend=mock_cache_backend,
            embedding_client=mock_embedding_client,
            vector_index=mock_vector_index,
            similarity_threshold=0.95,
            cache_ttl=None,
        )

    @pytest.mark.asyncio
    async def test_lookup_tier1_exact_match(
        self,
        semantic_cache: SemanticCacheStore,
        mock_cache_backend: MagicMock,
    ) -> None:
        query = "What is AI?"
        response = "AI is artificial intelligence"
        mock_cache_backend.get.return_value = response

        result = await semantic_cache.lookup(query)

        assert result == response
        expected_hash = hashlib.sha256(query.lower().strip().encode()).hexdigest()
        mock_cache_backend.get.assert_called_once_with(expected_hash)

    @pytest.mark.asyncio
    async def test_lookup_tier2_vector_match(
        self,
        semantic_cache: SemanticCacheStore,
        mock_cache_backend: MagicMock,
        mock_embedding_client: MagicMock,
        mock_vector_index: MagicMock,
    ) -> None:
        query = "What is AI?"
        response = "AI is artificial intelligence"
        similar_hash = hashlib.sha256(b"what is artificial intelligence").hexdigest()

        mock_cache_backend.get.side_effect = [None, response]
        mock_vector_index.search.return_value = [(similar_hash, 0.98)]

        result = await semantic_cache.lookup(query)

        assert result == response
        mock_embedding_client.embed.assert_called_once_with([query])
        mock_vector_index.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_lookup_tier3_cache_miss(
        self,
        semantic_cache: SemanticCacheStore,
        mock_cache_backend: MagicMock,
        mock_embedding_client: MagicMock,
        mock_vector_index: MagicMock,
    ) -> None:
        query = "What is AI?"

        mock_cache_backend.get.return_value = None
        mock_vector_index.search.return_value = []

        result = await semantic_cache.lookup(query)

        assert result is None
        mock_embedding_client.embed.assert_called_once()

    @pytest.mark.asyncio
    async def test_lookup_tier2_below_threshold(
        self,
        semantic_cache: SemanticCacheStore,
        mock_cache_backend: MagicMock,
        mock_embedding_client: MagicMock,
        mock_vector_index: MagicMock,
    ) -> None:
        query = "What is AI?"
        similar_hash = hashlib.sha256(b"what is something else").hexdigest()

        mock_cache_backend.get.return_value = None
        mock_vector_index.search.return_value = [(similar_hash, 0.85)]

        result = await semantic_cache.lookup(query)

        assert result is None
