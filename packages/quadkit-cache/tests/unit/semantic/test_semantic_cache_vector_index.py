"""FaissVectorIndex tests."""

from __future__ import annotations

import pytest

from quadkit.cache.semantic.vector_index import FaissVectorIndex


class TestFaissVectorIndex:
    """Test suite for FaissVectorIndex (mocking faiss)."""

    def test_faiss_index_init_valid_dims(self) -> None:
        pytest.importorskip("faiss")
        index = FaissVectorIndex(embedding_dim=384, max_entries=100_000)
        assert index.size == 0

    def test_faiss_index_init_invalid_dim(self) -> None:
        pytest.importorskip("faiss")
        with pytest.raises(ValueError, match="embedding_dim"):
            FaissVectorIndex(embedding_dim=0)

    def test_faiss_index_init_invalid_max_entries(self) -> None:
        pytest.importorskip("faiss")
        with pytest.raises(ValueError, match="max_entries"):
            FaissVectorIndex(max_entries=0)

    @pytest.mark.asyncio
    async def test_faiss_index_add_and_search(self) -> None:
        pytest.importorskip("faiss")
        index = FaissVectorIndex(embedding_dim=4)

        embedding1 = [1.0, 0.0, 0.0, 0.0]
        embedding2 = [0.7071, 0.7071, 0.0, 0.0]

        await index.add("key1", embedding1)
        await index.add("key2", embedding2)

        assert index.size == 2

        results = await index.search(embedding1, k=1)
        assert len(results) == 1
        assert results[0][0] == "key1"
        assert 0.95 < results[0][1] <= 1.0

    @pytest.mark.asyncio
    async def test_faiss_index_add_duplicate_key(self) -> None:
        pytest.importorskip("faiss")
        index = FaissVectorIndex(embedding_dim=4)
        embedding = [1.0, 0.0, 0.0, 0.0]

        await index.add("key1", embedding)
        assert index.size == 1

        await index.add("key1", embedding)
        assert index.size == 1

    @pytest.mark.asyncio
    async def test_faiss_index_remove(self) -> None:
        pytest.importorskip("faiss")
        index = FaissVectorIndex(embedding_dim=4)
        embedding = [1.0, 0.0, 0.0, 0.0]

        await index.add("key1", embedding)
        assert index.size == 1

        result = await index.remove("key1")
        assert result is True
        assert index.size == 0

    @pytest.mark.asyncio
    async def test_faiss_index_remove_not_found(self) -> None:
        pytest.importorskip("faiss")
        index = FaissVectorIndex(embedding_dim=4)

        result = await index.remove("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_faiss_index_search_empty_index(self) -> None:
        pytest.importorskip("faiss")
        index = FaissVectorIndex(embedding_dim=4)
        embedding = [1.0, 0.0, 0.0, 0.0]

        results = await index.search(embedding, k=1)
        assert results == []

    @pytest.mark.asyncio
    async def test_faiss_index_search_k_larger_than_entries(self) -> None:
        pytest.importorskip("faiss")
        index = FaissVectorIndex(embedding_dim=4)

        await index.add("key1", [1.0, 0.0, 0.0, 0.0])
        await index.add("key2", [0.7071, 0.7071, 0.0, 0.0])

        results = await index.search([1.0, 0.0, 0.0, 0.0], k=5)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_faiss_index_search_after_remove(self) -> None:
        pytest.importorskip("faiss")
        index = FaissVectorIndex(embedding_dim=4)

        await index.add("key1", [1.0, 0.0, 0.0, 0.0])
        await index.add("key2", [0.7071, 0.7071, 0.0, 0.0])

        await index.remove("key1")

        results = await index.search([1.0, 0.0, 0.0, 0.0], k=2)
        assert len(results) == 1
        assert results[0][0] == "key2"
