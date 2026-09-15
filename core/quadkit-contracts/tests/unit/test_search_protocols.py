"""Tests for search protocol definitions."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.search.protocols import (
    DatabaseSearchBackendProtocol,
    DocumentTransformerProtocol,
    SearchableProtocol,
    SearchAnalyticsProtocol,
    SearchEngineProtocol,
)


class TestSearchEngineProtocol:
    """Tests for SearchEngineProtocol."""

    @pytest.mark.asyncio
    async def test_has_search_method(self) -> None:
        """Test protocol has index-scoped search async method."""

        class Engine:
            async def search(
                self,
                index: str,
                query: str,
                filters: dict[str, Any] | None = None,
                limit: int = 20,
                offset: int = 0,
                sort: list[str] | None = None,
                **kwargs: Any,
            ) -> Any:
                return {"hits": [], "total": 0}

        engine = Engine()
        result = await engine.search("test_index", "test")
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_has_index_document_method(self) -> None:
        """Test protocol has index-scoped index_document async method."""

        class Engine:
            async def index_document(
                self,
                index: str,
                document_id: str,
                document: dict[str, Any],
                **kwargs: Any,
            ) -> None:
                pass

        engine = Engine()
        await engine.index_document("test_index", "id1", {"title": "Test"})

    @pytest.mark.asyncio
    async def test_has_index_many_method(self) -> None:
        """Test protocol has index-scoped index_many async method."""

        class Engine:
            async def index_many(
                self,
                index: str,
                documents: list[tuple[str, dict[str, Any]]],
                **kwargs: Any,
            ) -> None:
                pass

        engine = Engine()
        await engine.index_many("test_index", [("id1", {"title": "Test"})])

    @pytest.mark.asyncio
    async def test_has_delete_document_method(self) -> None:
        """Test protocol has index-scoped delete_document async method."""

        class Engine:
            async def delete_document(
                self,
                index: str,
                document_id: str,
                **kwargs: Any,
            ) -> None:
                pass

        engine = Engine()
        await engine.delete_document("test_index", "id1")

    @pytest.mark.asyncio
    async def test_has_health_check_method(self) -> None:
        """Test protocol has health_check async method."""

        class Engine:
            async def health_check(self, timeout: float = 5.0) -> Any:
                return {"status": "healthy"}

        engine = Engine()
        result = await engine.health_check()
        assert result["status"] == "healthy"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable (canonical index-scoped shape)."""

        class Engine:
            async def search(self, index: str, query: str, **kwargs: Any) -> Any:
                return {}

            async def index_document(
                self, index: str, doc_id: str, doc: dict, **kwargs: Any
            ) -> None:
                pass

            async def index_many(self, index: str, docs: list, **kwargs: Any) -> None:
                pass

            async def get_document(self, index: str, doc_id: str, **kwargs: Any) -> Any:
                return None

            async def delete_document(self, index: str, doc_id: str, **kwargs: Any) -> None:
                pass

            async def create_index(self, index: str, **kwargs: Any) -> Any:
                return {}

            async def delete_index(self, index: str, **kwargs: Any) -> Any:
                return {}

            async def index_exists(self, index: str, **kwargs: Any) -> Any:
                return True

            async def health_check(self, timeout: float = 5.0) -> Any:
                return {}

        assert isinstance(Engine(), SearchEngineProtocol)


class TestIndexManagerProtocol:
    """Tests for IndexManagerProtocol."""

    @pytest.mark.asyncio
    async def test_has_create_index_method(self) -> None:
        """Test protocol has create_index async method."""

        class Manager:
            async def create_index(
                self,
                index_name: str,
                schema: dict[str, Any],
            ) -> None:
                pass

        manager = Manager()
        await manager.create_index("test_index", {"properties": {}})

    @pytest.mark.asyncio
    async def test_has_delete_index_method(self) -> None:
        """Test protocol has delete_index async method."""

        class Manager:
            async def delete_index(self, index_name: str) -> None:
                pass

        manager = Manager()
        await manager.delete_index("test_index")

    @pytest.mark.asyncio
    async def test_has_get_index_info_method(self) -> None:
        """Test protocol has get_index_info async method."""

        class Manager:
            async def get_index_info(self, index_name: str) -> dict[str, Any]:
                return {"name": index_name}

        manager = Manager()
        result = await manager.get_index_info("test_index")
        assert result["name"] == "test_index"

    @pytest.mark.asyncio
    async def test_has_index_exists_method(self) -> None:
        """Test protocol has index_exists async method."""

        class Manager:
            async def index_exists(self, index_name: str) -> bool:
                return True

        manager = Manager()
        result = await manager.index_exists("test_index")
        assert result is True


class TestSearchableProtocol:
    """Tests for SearchableProtocol."""

    def test_has_search_document_id_property(self) -> None:
        """Test protocol has search_document_id property."""

        class Searchable:
            @property
            def search_document_id(self) -> str:
                return "doc-123"

        obj = Searchable()
        assert obj.search_document_id == "doc-123"

    def test_has_search_document_property(self) -> None:
        """Test protocol has search_document property."""

        class Searchable:
            @property
            def search_document(self) -> dict[str, Any]:
                return {"title": "Test"}

        obj = Searchable()
        assert obj.search_document["title"] == "Test"

    def test_has_search_index_name_property(self) -> None:
        """Test protocol has search_index_name property."""

        class Searchable:
            @property
            def search_index_name(self) -> str:
                return "test_index"

        obj = Searchable()
        assert obj.search_index_name == "test_index"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Searchable:
            @property
            def search_document_id(self) -> str:
                return ""

            @property
            def search_document(self) -> dict:
                return {}

            @property
            def search_index_name(self) -> str:
                return ""

        assert isinstance(Searchable(), SearchableProtocol)


class TestSearchAnalyticsProtocol:
    """Tests for SearchAnalyticsProtocol."""

    @pytest.mark.asyncio
    async def test_has_record_search_method(self) -> None:
        """Test protocol has record_search async method."""

        class Analytics:
            async def record_search(
                self,
                query: str,
                filters: dict[str, Any] | None,
                result_count: int,
                user_id: str | None = None,
                session_id: str | None = None,
            ) -> None:
                pass

        analytics = Analytics()
        await analytics.record_search("test", None, 10)

    @pytest.mark.asyncio
    async def test_has_get_search_metrics_method(self) -> None:
        """Test protocol has get_search_metrics async method."""

        class Analytics:
            async def get_search_metrics(
                self,
                time_range: dict[str, Any] | None = None,
            ) -> dict[str, Any]:
                return {"total_searches": 0}

        analytics = Analytics()
        result = await analytics.get_search_metrics()
        assert result["total_searches"] == 0

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Analytics:
            async def record_search(
                self, query: str, filters: Any, result_count: int, **kwargs: Any
            ) -> None:
                pass

            async def get_search_metrics(self, time_range: Any = None) -> dict:
                return {}

        assert isinstance(Analytics(), SearchAnalyticsProtocol)


class TestDatabaseSearchBackendProtocol:
    """Tests for DatabaseSearchBackendProtocol."""

    @pytest.mark.asyncio
    async def test_has_connect_method(self) -> None:
        """Test protocol has connect async method."""

        class Backend:
            async def connect(self) -> None:
                pass

        backend = Backend()
        await backend.connect()

    @pytest.mark.asyncio
    async def test_has_close_method(self) -> None:
        """Test protocol has close async method."""

        class Backend:
            async def close(self) -> None:
                pass

        backend = Backend()
        await backend.close()

    @pytest.mark.asyncio
    async def test_has_ensure_schema_method(self) -> None:
        """Test protocol has ensure_schema async method."""

        class Backend:
            async def ensure_schema(self, index_name: str) -> None:
                pass

        backend = Backend()
        await backend.ensure_schema("test_index")

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Backend:
            async def connect(self) -> None:
                pass

            async def close(self) -> None:
                pass

            async def ensure_schema(self, index_name: str) -> None:
                pass

        assert isinstance(Backend(), DatabaseSearchBackendProtocol)


class TestDocumentTransformerProtocol:
    """Tests for DocumentTransformerProtocol."""

    def test_has_transform_method(self) -> None:
        """Test protocol has transform method."""

        class Transformer:
            def transform(self, entity: Any) -> dict[str, Any]:
                return {"id": "test"}

        transformer = Transformer()
        result = transformer.transform({"id": "test"})
        assert result["id"] == "test"

    def test_has_transform_batch_method(self) -> None:
        """Test protocol has transform_batch method."""

        class Transformer:
            def transform_batch(self, entities: list[Any]) -> list[dict[str, Any]]:
                return [{"id": e["id"]} for e in entities]

        transformer = Transformer()
        result = transformer.transform_batch([{"id": "1"}])
        assert len(result) == 1

    def test_has_extract_text_method(self) -> None:
        """Test protocol has extract_text method."""

        class Transformer:
            def extract_text(self, content: Any) -> str:
                return str(content)

        transformer = Transformer()
        result = transformer.extract_text("test content")
        assert result == "test content"

    def test_is_runtime_checkable(self) -> None:
        """Test protocol is runtime checkable."""

        class Transformer:
            def transform(self, entity: Any) -> dict:
                return {}

            def transform_batch(self, entities: list[Any]) -> list[dict]:
                return []

            def extract_text(self, content: Any) -> str:
                return ""

        assert isinstance(Transformer(), DocumentTransformerProtocol)
