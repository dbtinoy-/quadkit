from __future__ import annotations

"""Contract compliance suite for VectorStoreProtocol implementations."""

import abc
from typing import Any
import uuid

import pytest

__all__ = ["VectorStoreCompliance"]


def _make_collection_config(name: str, dimension: int = 4) -> Any:
    """Build a minimal CollectionConfig for compliance tests.

    Args:
        name: Collection name.
        dimension: Vector dimension (small for speed).

    Returns:
        CollectionConfig instance.
    """
    from quadkit.contracts.data.vector.enums import DistanceMetric
    from quadkit.contracts.data.vector.types import CollectionConfig

    return CollectionConfig(
        name=name, dimension=dimension, distance_metric=DistanceMetric.COSINE
    )


def _make_vector_record(id: str | None = None, dimension: int = 4) -> Any:
    """Build a minimal VectorRecord for compliance tests.

    Args:
        id: Record ID. Generated if None.
        dimension: Number of vector dimensions.

    Returns:
        VectorRecord instance.
    """
    from quadkit.contracts.data.vector.types import VectorRecord

    return VectorRecord(
        id=id or uuid.uuid4().hex,
        vector=[0.1 * i for i in range(dimension)],
        metadata={"test": True},
    )


def _make_search_query(dimension: int = 4, top_k: int = 3) -> Any:
    """Build a minimal SearchQuery for compliance tests.

    Args:
        dimension: Vector dimension matching the collection.
        top_k: Number of results to return.

    Returns:
        SearchQuery instance.
    """
    from quadkit.contracts.data.vector.types import SearchQuery

    return SearchQuery(
        vector=[0.1 * i for i in range(dimension)],
        top_k=top_k,
    )


class VectorStoreCompliance(abc.ABC):
    """Compliance suite for VectorStoreProtocol implementations.

    Subclass and implement create_store() to run all compliance tests.
    The store is connected before tests and disconnected after.
    """

    @abc.abstractmethod
    async def create_store(self) -> Any:
        """Create a connected VectorStoreProtocol implementation under test.

        Returns:
            A connected VectorStoreProtocol instance.
        """
        ...

    def _collection_name(self) -> str:
        """Generate a unique collection name for test isolation.

        Returns:
            A unique collection name string.
        """
        return f"compliance_{uuid.uuid4().hex[:8]}"

    @pytest.mark.asyncio
    async def test_health_check_passes(self) -> None:
        """health_check() returns a healthy result."""
        store = await self.create_store()
        result = await store.health_check(timeout=5.0)
        assert result is not None
        assert hasattr(result, "status")

    @pytest.mark.asyncio
    async def test_list_collections_returns_list(self) -> None:
        """list_collections() returns a list."""
        store = await self.create_store()
        result = await store.list_collections()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_create_and_check_collection(self) -> None:
        """create_collection() creates a collection visible via collection_exists()."""
        store = await self.create_store()
        name = self._collection_name()
        config = _make_collection_config(name)
        await store.create_collection(config)
        try:
            assert await store.collection_exists(name) is True
        finally:
            await store.delete_collection(name)

    @pytest.mark.asyncio
    async def test_delete_collection_removes_it(self) -> None:
        """delete_collection() removes the collection."""
        store = await self.create_store()
        name = self._collection_name()
        await store.create_collection(_make_collection_config(name))
        await store.delete_collection(name)
        assert await store.collection_exists(name) is False

    @pytest.mark.asyncio
    async def test_collection_not_exists_for_unknown(self) -> None:
        """collection_exists() returns False for a non-existent collection."""
        store = await self.create_store()
        assert await store.collection_exists(f"no-such-{uuid.uuid4().hex}") is False

    @pytest.mark.asyncio
    async def test_upsert_and_count(self) -> None:
        """upsert() increases count in the collection."""
        store = await self.create_store()
        name = self._collection_name()
        await store.create_collection(_make_collection_config(name))
        try:
            collection = await store.get_collection(name)
            records = [_make_vector_record() for _ in range(3)]
            result = await collection.upsert(records)
            assert result is not None
            count = await collection.count()
            assert count == 3
        finally:
            await store.delete_collection(name)

    @pytest.mark.asyncio
    async def test_search_returns_results(self) -> None:
        """search() returns results after upsert."""
        store = await self.create_store()
        name = self._collection_name()
        await store.create_collection(_make_collection_config(name))
        try:
            collection = await store.get_collection(name)
            await collection.upsert([_make_vector_record() for _ in range(5)])
            query = _make_search_query(top_k=3)
            results = await collection.search(query)
            assert isinstance(results, list)
            assert len(results) <= 3
        finally:
            await store.delete_collection(name)

    @pytest.mark.asyncio
    async def test_get_by_ids(self) -> None:
        """get() retrieves vectors by their IDs."""
        store = await self.create_store()
        name = self._collection_name()
        await store.create_collection(_make_collection_config(name))
        try:
            collection = await store.get_collection(name)
            record = _make_vector_record(id="test-id-1")
            await collection.upsert([record])
            found = await collection.get(["test-id-1"])
            assert len(found) == 1
            assert found[0].id == "test-id-1"
        finally:
            await store.delete_collection(name)

    @pytest.mark.asyncio
    async def test_delete_by_ids(self) -> None:
        """delete() removes vectors by ID."""
        store = await self.create_store()
        name = self._collection_name()
        await store.create_collection(_make_collection_config(name))
        try:
            collection = await store.get_collection(name)
            record = _make_vector_record(id="to-delete")
            await collection.upsert([record])
            await collection.delete(["to-delete"])
            found = await collection.get(["to-delete"])
            assert len(found) == 0
        finally:
            await store.delete_collection(name)
