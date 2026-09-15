"""
Search testing infrastructure - core classes and mocks.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.testing.testkit.environment import TestEnvironment

try:
    from quadkit.search import (
        SearchConfig,
        SearchResponse,
    )
except ImportError:
    from typing import Any

    # Fallback for environments without installed search package
    SearchConfig = Any  # type: ignore[misc,assignment]
    SearchResponse = Any  # type: ignore[misc,assignment]
    SearchResult = Any


class SearchTestData:
    """Test data for search components."""

    @staticmethod
    def sample_searchable_documents() -> list[dict[str, Any]]:
        """Get sample searchable documents for testing."""
        return [
            {
                "id": "doc_1",
                "title": "Python Programming Guide",
                "content": "Learn Python programming with comprehensive examples",
                "author": "John Doe",
                "tags": ["python", "programming", "tutorial"],
                "category": "education",
                "published_at": "2024-01-15T10:00:00Z",
            },
            {
                "id": "doc_2",
                "title": "Advanced GraphQL",
                "content": "Master GraphQL with federation and advanced patterns",
                "author": "Jane Smith",
                "tags": ["graphql", "api", "federation"],
                "category": "technology",
                "published_at": "2024-02-20T14:30:00Z",
            },
            {
                "id": "doc_3",
                "title": "Machine Learning Basics",
                "content": "Introduction to machine learning algorithms and concepts",
                "author": "Bob Johnson",
                "tags": ["ml", "ai", "algorithms"],
                "category": "technology",
                "published_at": "2024-03-10T09:15:00Z",
            },
        ]

    @staticmethod
    def sample_search_queries() -> list[dict[str, Any]]:
        """Get sample search queries for testing."""
        return [
            {
                "query": "python programming",
                "filters": {"category": "education"},
                "expected_results": ["doc_1"],
            },
            {"query": "graphql", "filters": {}, "expected_results": ["doc_2"]},
            {
                "query": "machine learning",
                "filters": {"tags": ["ml", "ai"]},
                "expected_results": ["doc_3"],
            },
            {"query": "nonexistent content", "filters": {}, "expected_results": []},
        ]

    @staticmethod
    def sample_search_results() -> list[dict[str, Any]]:
        """Get sample search results for testing."""
        return [
            {
                "document": {
                    "id": "doc_1",
                    "title": "Python Programming Guide",
                    "content": "Learn Python programming with comprehensive examples",
                },
                "score": 0.95,
                "highlights": {
                    "title": ["<mark>Python</mark> Programming Guide"],
                    "content": ["Learn <mark>Python</mark> programming"],
                },
            },
            {
                "document": {
                    "id": "doc_2",
                    "title": "Advanced GraphQL",
                    "content": "Master GraphQL with federation and advanced patterns",
                },
                "score": 0.87,
                "highlights": {"title": ["Advanced <mark>GraphQL</mark>"]},
            },
        ]

    @staticmethod
    def sample_index_configs() -> list[dict[str, Any]]:
        """Get sample index configurations for testing."""
        return [
            {
                "name": "articles",
                "settings": {
                    "replicas": 1,
                    "shards": 3,
                    "analysis": {"analyzer": "standard"},
                },
                "mappings": {
                    "properties": {
                        "title": {"type": "text", "analyzer": "standard"},
                        "content": {"type": "text", "analyzer": "standard"},
                        "author": {"type": "keyword"},
                        "tags": {"type": "keyword"},
                        "category": {"type": "keyword"},
                        "published_at": {"type": "date"},
                    },
                },
            },
            {
                "name": "products",
                "settings": {"replicas": 0, "shards": 1},
                "mappings": {
                    "properties": {
                        "name": {"type": "text"},
                        "description": {"type": "text"},
                        "price": {"type": "float"},
                        "category": {"type": "keyword"},
                    },
                },
            },
        ]


class MockSearchBackend:
    """Mock search backend for testing."""

    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}
        self.indices: dict[str, dict[str, Any]] = {}
        self.search_calls: list[dict[str, Any]] = []

    async def create_index(self, name: str, config: dict[str, Any]) -> None:
        """Mock index creation."""
        self.indices[name] = config

    async def delete_index(self, name: str) -> None:
        """Mock index deletion."""
        self.indices.pop(name, None)

    async def index_exists(self, name: str) -> bool:
        """Mock index existence check."""
        return name in self.indices

    async def index_document(
        self,
        index: str,
        doc_id: str,
        document: dict[str, Any],
    ) -> None:
        """Mock document indexing."""
        if index not in self.documents:
            self.documents[index] = {}
        self.documents[index][doc_id] = document

    async def delete_document(self, index: str, doc_id: str) -> None:
        """Mock document deletion."""
        if index in self.documents:
            self.documents[index].pop(doc_id, None)

    async def search(
        self,
        index: str,
        query: str,
        filters: dict[str, Any] | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Mock search operation."""
        search_call = {
            "index": index,
            "query": query,
            "filters": filters or {},
            "limit": limit,
            "offset": offset,
            "timestamp": asyncio.get_event_loop().time(),
        }
        self.search_calls.append(search_call)

        # Simple mock search logic
        results = []
        if index in self.documents:
            docs = list(self.documents[index].values())
            # Filter by query (simple substring match)
            if query:
                docs = list(filter(lambda d: query.lower() in str(d).lower(), docs))

            # Apply filters
            if filters:
                filtered_docs = []
                for doc in docs:
                    match = True
                    for key, value in filters.items():
                        if key not in doc or doc[key] != value:
                            match = False
                            break
                    if match:
                        filtered_docs.append(doc)
                docs = filtered_docs

            # Convert to search results format
            for doc in docs[offset : offset + limit]:
                results.append({"document": doc, "score": 0.9, "highlights": {}})

        return {"results": results, "total": len(results), "took": 10, "query": query}

    async def get_document(self, index: str, doc_id: str) -> dict[str, Any] | None:
        """Mock document retrieval."""
        if index in self.documents and doc_id in self.documents[index]:
            return cast("dict[str, Any] | None", self.documents[index][doc_id])
        return None

    async def bulk_index(self, index: str, documents: list[dict[str, Any]]) -> None:
        """Mock bulk indexing."""
        if index not in self.documents:
            self.documents[index] = {}
        for doc in documents:
            doc_id = doc.get("id", str(id(doc)))
            self.documents[index][doc_id] = doc

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Mock health check."""
        return HealthCheckResult(
            component="mock",
            status=HealthStatus.HEALTHY,
            details={"backend": "mock"},
        )

    def get_search_calls(self) -> list[dict[str, Any]]:
        """Get recorded search calls."""
        return self.search_calls.copy()


class SearchTestBed(TestEnvironment):
    """Test bed for search components."""

    def __init__(self, config: SearchConfig | None = None):
        """Initialize search test bed."""
        super().__init__()
        self.config = config or SearchConfig(provider="elasticsearch", timeout=30.0)
        self._mock_backend = MockSearchBackend()
        self._indexed_documents: list[dict[str, Any]] = []
        self._search_operations: list[dict[str, Any]] = []

    async def setup(self) -> None:  # type: ignore[override]
        """Set up the test bed."""
        await super().setup()
        # Pre-populate with test data
        for doc in SearchTestData.sample_searchable_documents():
            self._indexed_documents.append(doc)

        # Create default index
        await self._mock_backend.create_index("test_index", {})

    async def teardown(self) -> None:  # type: ignore[override]
        """Tear down the test bed."""
        self._indexed_documents.clear()
        self._search_operations.clear()
        super().teardown()

    @property
    def mock_backend(self) -> MockSearchBackend:
        """Get the mock search backend."""
        return self._mock_backend

    def get_indexed_documents(self) -> list[dict[str, Any]]:
        """Get documents indexed during testing."""
        return self._indexed_documents.copy()

    def get_search_operations(self) -> list[dict[str, Any]]:
        """Get search operations performed during testing."""
        return self._search_operations.copy()

    async def simulate_document_indexing(
        self,
        index: str,
        document: dict[str, Any],
    ) -> None:
        """Simulate document indexing."""
        await self._mock_backend.index_document(
            index,
            document.get("id", "test_id"),
            document,
        )
        self._indexed_documents.append(document)

    async def simulate_search_operation(
        self,
        index: str,
        query: str,
        filters: dict[str, Any] | None = None,
        results: list[dict[str, Any]] | None = None,
    ) -> None:
        """Simulate search operation."""
        operation = {
            "index": index,
            "query": query,
            "filters": filters or {},
            "results": results or [],
            "timestamp": asyncio.get_event_loop().time(),
        }
        self._search_operations.append(operation)


class SearchTestClient:
    """Test client for search components."""

    def __init__(self, test_bed: SearchTestBed):
        """Initialize test client."""
        self.test_bed = test_bed
        self.backend: MockSearchBackend = test_bed.mock_backend

    async def start_provider(
        self,
        backend_type: str = "mock",
        index_name: str = "test_index",
    ) -> MockSearchBackend:
        """Start a search provider for testing."""
        # Create default index
        await self.backend.create_index(index_name, {})
        return self.backend

    async def stop_provider(self) -> None:
        """Stop the search provider."""
        # No cleanup needed for mock backend

    async def create_search_engine(
        self,
        index_name: str = "test_index",
    ) -> MockSearchBackend:
        """Create a search engine for testing."""
        await self.backend.create_index(index_name, {})
        return self.backend

    async def index_test_documents(
        self,
        documents: list[dict[str, Any]] | None = None,
        index_name: str = "test_index",
    ) -> None:
        """Index test documents."""
        docs = documents or SearchTestData.sample_searchable_documents()
        for doc in docs:
            await self.backend.index_document(index_name, doc["id"], doc)
            await self.test_bed.simulate_document_indexing(index_name, doc)

    async def perform_test_search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        index_name: str = "test_index",
        limit: int = 10,
    ) -> SearchResponse:
        """Perform a test search."""
        result = await self.backend.search(
            index_name,
            query,
            filters=filters,
            limit=limit,
        )

        # Convert mock backend results to SearchResponse
        search_results = [
            SearchResult(
                id=r["document"].get("id", ""),
                score=r["score"],
                data=r["document"],
                highlights=r.get("highlights"),
            )
            for r in result["results"]
        ]

        response = SearchResponse(
            results=search_results,
            total=result["total"],
            took_ms=result.get("took") or result.get("took_ms"),
        )

        await self.test_bed.simulate_search_operation(
            index_name,
            query,
            filters,
            search_results,
        )
        return response

    async def verify_search_results(
        self,
        query: str,
        expected_doc_ids: list[str],
        filters: dict[str, Any] | None = None,
        index_name: str = "test_index",
    ) -> bool:
        """Verify search results contain expected documents."""
        response = await self.perform_test_search(query, filters, index_name)
        result_ids = [result.id for result in response.results]
        return set(expected_doc_ids).issubset(set(result_ids))

    @asynccontextmanager
    async def search_context(
        self,
        backend_type: str = "mock",
        index_name: str = "test_index",
    ) -> AsyncGenerator[MockSearchBackend, None]:
        """Async context manager for search testing."""
        backend = await self.start_provider(backend_type, index_name)
        try:
            yield backend
        finally:
            await self.stop_provider()
