"""Contract compliance suite for ``SearchEngineProtocol`` implementations.

Subclass :class:`SearchEngineCompliance` and implement
:meth:`create_engine` to verify any search engine satisfies the
``SearchEngineProtocol`` contract::

    from quadkit.testing.compliance import SearchEngineCompliance

    class TestMySearchEngine(SearchEngineCompliance):
        async def create_engine(self):
            return MySearchEngine(url="http://localhost:9200")
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

import pytest

__all__ = ["SearchEngineCompliance"]


class SearchEngineCompliance:
    """Reusable test suite for any ``SearchEngineProtocol`` implementation.

    Subclass and implement :meth:`create_engine`:

    .. code-block:: python

        class TestMySearch(SearchEngineCompliance):
            async def create_engine(self):
                return MySearchEngine(url="http://localhost:9200")
    """

    INDEX_NAME = "compliance_test_index"

    @abstractmethod
    async def create_engine(self) -> Any:
        """Return a ready-to-use search engine under test."""
        ...

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_and_delete_index(self) -> None:
        """create_index and delete_index do not raise errors."""
        engine = await self.create_engine()
        await engine.create_index(self.INDEX_NAME)
        await engine.delete_index(self.INDEX_NAME)

    # ------------------------------------------------------------------
    # Indexing documents
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_index_single_document(self) -> None:
        """index_document succeeds and the document is searchable."""
        engine = await self.create_engine()
        await engine.create_index(self.INDEX_NAME)
        try:
            await engine.index_document(
                index_name=self.INDEX_NAME,
                document_id="doc-1",
                document={"title": "Compliance test"},
            )
        finally:
            await engine.delete_index(self.INDEX_NAME)

    @pytest.mark.asyncio
    async def test_index_many_documents(self) -> None:
        """index_many successfully indexes multiple documents."""
        engine = await self.create_engine()
        await engine.create_index(self.INDEX_NAME)
        try:
            docs = [
                {"id": "bulk-1", "document": {"title": "Alpha"}},
                {"id": "bulk-2", "document": {"title": "Beta"}},
            ]
            await engine.index_many(index_name=self.INDEX_NAME, documents=docs)
        finally:
            await engine.delete_index(self.INDEX_NAME)

    # ------------------------------------------------------------------
    # Delete documents
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_document(self) -> None:
        """delete_document removes an indexed document without error."""
        engine = await self.create_engine()
        await engine.create_index(self.INDEX_NAME)
        try:
            await engine.index_document(
                index_name=self.INDEX_NAME,
                document_id="doc-del",
                document={"title": "To be deleted"},
            )
            await engine.delete_document(
                index_name=self.INDEX_NAME, document_id="doc-del"
            )
        finally:
            await engine.delete_index(self.INDEX_NAME)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_search_returns_results_object(self) -> None:
        """search returns an object with a hits or results attribute."""
        engine = await self.create_engine()
        await engine.create_index(self.INDEX_NAME)
        try:
            await engine.index_document(
                index_name=self.INDEX_NAME,
                document_id="s-1",
                document={"title": "SearchableProtocol"},
            )
            results = await engine.search(
                index_name=self.INDEX_NAME, query={"query": "SearchableProtocol"}
            )
            assert results is not None
        finally:
            await engine.delete_index(self.INDEX_NAME)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_health_check_returns_result(self) -> None:
        """health_check returns a HealthCheckResult."""
        engine = await self.create_engine()
        result = await engine.health_check(timeout=5.0)
        assert result is not None
        assert hasattr(result, "status")
