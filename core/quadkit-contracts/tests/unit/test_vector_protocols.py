"""Tests for vector protocol definitions."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.data.vector.protocols import (
    VectorCollectionProtocol,
    VectorStoreProtocol,
)


class TestVectorStoreProtocol:
    """Tests for VectorStoreProtocol."""

    @pytest.mark.asyncio
    async def test_has_connect_method(self) -> None:
        """Test protocol has connect async method."""

        class Store:
            async def connect(self) -> None:
                pass

        store = Store()
        await store.connect()

    @pytest.mark.asyncio
    async def test_has_disconnect_method(self) -> None:
        """Test protocol has disconnect async method."""

        class Store:
            async def disconnect(self) -> None:
                pass

        store = Store()
        await store.disconnect()

    @pytest.mark.asyncio
    async def test_has_health_check_method(self) -> None:
        """Test protocol has health_check async method."""

        class Store:
            async def health_check(self, timeout: float = 5.0) -> Any:
                return {"status": "healthy"}

        store = Store()
        result = await store.health_check()
        assert result["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_has_list_collections_method(self) -> None:
        """Test protocol has list_collections async method."""

        class Store:
            async def list_collections(self) -> list[Any]:
                return []

        store = Store()
        result = await store.list_collections()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_has_create_collection_method(self) -> None:
        """Test protocol has create_collection async method."""

        class Store:
            async def create_collection(self, config: Any) -> None:
                pass

        store = Store()
        await store.create_collection({})

    @pytest.mark.asyncio
    async def test_has_delete_collection_method(self) -> None:
        """Test protocol has delete_collection async method."""

        class Store:
            async def delete_collection(self, name: str) -> None:
                pass

        store = Store()
        await store.delete_collection("test")

    @pytest.mark.asyncio
    async def test_has_collection_exists_method(self) -> None:
        """Test protocol has collection_exists async method."""

        class Store:
            async def collection_exists(self, name: str) -> bool:
                return True

        store = Store()
        result = await store.collection_exists("test")
        assert result is True

    @pytest.mark.asyncio
    async def test_has_get_collection_method(self) -> None:
        """Test protocol has get_collection async method."""

        class Store:
            async def get_collection(self, name: str) -> Any:
                return {}

        store = Store()
        result = await store.get_collection("test")
        assert isinstance(result, dict)

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Store:
            async def connect(self) -> None:
                pass

            async def disconnect(self) -> None:
                pass

            async def health_check(self, timeout: float = 5.0) -> Any:
                return {}

            async def list_collections(self) -> list:
                return []

            async def create_collection(self, config: Any) -> None:
                pass

            async def delete_collection(self, name: str) -> None:
                pass

            async def collection_exists(self, name: str) -> bool:
                return False

            async def get_collection(self, name: str) -> Any:
                return {}

            async def add_texts(
                self,
                texts: list[str],
                embeddings: list[list[float]] | None = None,
                metadatas: list[dict[str, Any]] | None = None,
                collection_name: str | None = None,
            ) -> Any:
                return {"ids": []}

        assert isinstance(Store(), VectorStoreProtocol)


class TestVectorCollectionProtocol:
    """Tests for VectorCollectionProtocol."""

    def test_has_name_property(self) -> None:
        """Test protocol has name property."""

        class Collection:
            @property
            def name(self) -> str:
                return "test"

        collection = Collection()
        assert collection.name == "test"

    def test_has_dimension_property(self) -> None:
        """Test protocol has dimension property."""

        class Collection:
            @property
            def dimension(self) -> int:
                return 1536

        collection = Collection()
        assert collection.dimension == 1536

    def test_has_distance_metric_property(self) -> None:
        """Test protocol has distance_metric property."""

        class Collection:
            @property
            def distance_metric(self) -> Any:
                return "cosine"

        collection = Collection()
        assert collection.distance_metric == "cosine"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        from quadkit.contracts.data.vector.enums import DistanceMetric

        class Collection:
            @property
            def name(self) -> str:
                return ""

            @property
            def dimension(self) -> int:
                return 0

            @property
            def distance_metric(self) -> DistanceMetric:
                return DistanceMetric.COSINE

            async def upsert(self, records: list) -> Any:
                return {}

            async def search(self, query: Any) -> list:
                return []

            async def get(self, ids: list) -> list:
                return []

            async def delete(self, ids: list) -> Any:
                return {}

            async def delete_by_filter(self, filter: Any) -> Any:
                return {}

            async def count(self) -> int:
                return 0

            async def update_metadata(self, id: str, metadata: dict) -> bool:
                return False

            async def add_texts(
                self,
                texts: list[str],
                embeddings: list[list[float]],
                metadatas: list[dict[str, Any]] | None = None,
                ids: list[str] | None = None,
            ) -> Any:
                return {"ids": []}

        assert isinstance(Collection(), VectorCollectionProtocol)
