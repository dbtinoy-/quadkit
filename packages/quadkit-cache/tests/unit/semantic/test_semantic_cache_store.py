"""SemanticCacheStore store/write tests."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.cache.semantic.store import SemanticCacheStore


class TestSemanticCacheStore:
    """Test suite for SemanticCacheStore store operations."""

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
    async def test_store_writes_both_tiers(
        self,
        semantic_cache: SemanticCacheStore,
        mock_cache_backend: MagicMock,
        mock_embedding_client: MagicMock,
        mock_vector_index: MagicMock,
    ) -> None:
        query = "What is AI?"
        response = "AI is artificial intelligence"

        await semantic_cache.store(query, response, "gpt-4")

        expected_hash = hashlib.sha256(query.lower().strip().encode()).hexdigest()
        mock_cache_backend.set.assert_called_once_with(
            expected_hash, response, ttl=None
        )
        mock_embedding_client.embed.assert_called_once_with([query])
        mock_vector_index.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_removes_from_both_tiers(
        self,
        semantic_cache: SemanticCacheStore,
        mock_cache_backend: MagicMock,
        mock_vector_index: MagicMock,
    ) -> None:
        query = "What is AI?"
        expected_hash = hashlib.sha256(query.lower().strip().encode()).hexdigest()

        mock_cache_backend.delete.return_value = True
        mock_vector_index.remove.return_value = True

        result = await semantic_cache.invalidate(query)

        assert result is True
        mock_cache_backend.delete.assert_called_once_with(expected_hash)
        mock_vector_index.remove.assert_called_once_with(expected_hash)

    @pytest.mark.asyncio
    async def test_invalidate_not_found(
        self,
        semantic_cache: SemanticCacheStore,
        mock_cache_backend: MagicMock,
        mock_vector_index: MagicMock,
    ) -> None:
        query = "What is AI?"

        mock_cache_backend.delete.return_value = False
        mock_vector_index.remove.return_value = False

        result = await semantic_cache.invalidate(query)

        assert result is False

    def test_normalize_query_strips_and_lowercases(self) -> None:
        normalized = SemanticCacheStore._normalize_query("  Hello World  ")
        assert normalized == "hello world"

    def test_semantic_cache_init_invalid_threshold(self) -> None:
        with pytest.raises(ValueError, match="similarity_threshold"):
            SemanticCacheStore(
                cache_backend=MagicMock(),
                embedding_client=MagicMock(),
                vector_index=MagicMock(),
                similarity_threshold=1.5,
            )

    @pytest.mark.asyncio
    async def test_store_with_ttl(
        self,
        semantic_cache: SemanticCacheStore,
        mock_cache_backend: MagicMock,
    ) -> None:
        semantic_cache._cache_ttl = 300

        query = "What is AI?"
        response = "AI is artificial intelligence"

        await semantic_cache.store(query, response, "gpt-4")

        call_args = mock_cache_backend.set.call_args
        assert call_args.kwargs.get("ttl") == 300
