"""In-memory search engine for testing and compliance suites.

Provides :class:`InMemorySearchEngine`, a dependency-free index manager
and full-text-ish search engine implementing the engine contract used by
:class:`~quadkit.testing.compliance.SearchEngineCompliance`
(``index_name`` keyword arguments, dict-based bulk documents, and a
``query`` mapping for :meth:`search`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quadkit.contracts.core.health import HealthCheckResult, HealthStatus

__all__ = ["InMemorySearchEngine", "SearchResults"]


@dataclass
class SearchResults:
    """Search result container with ``hits`` and ``total`` fields."""

    hits: list[dict[str, Any]] = field(default_factory=list)
    total: int = 0

    @property
    def results(self) -> list[dict[str, Any]]:
        """Alias of :attr:`hits` for callers expecting that attribute."""
        return self.hits


class InMemorySearchEngine:
    """In-memory search engine with simple substring matching.

    Documents are stored per index by document ID.  ``search`` matches
    documents whose serialised content contains the query string.

    Example::

        engine = InMemorySearchEngine()
        await engine.create_index("docs")
        await engine.index_document(
            index_name="docs", document_id="1", document={"title": "Hello"}
        )
        results = await engine.search(index_name="docs", query={"query": "Hello"})
        assert results.total == 1
    """

    def __init__(self) -> None:
        self._indexes: dict[str, dict[str, dict[str, Any]]] = {}

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    async def create_index(self, name: str) -> None:
        """Create an empty index.

        Args:
            name: Index name.
        """
        self._indexes.setdefault(name, {})

    async def delete_index(self, name: str) -> None:
        """Delete an index and all of its documents.

        Args:
            name: Index name (unknown names are ignored).
        """
        self._indexes.pop(name, None)

    async def index_exists(self, name: str) -> bool:
        """Return ``True`` when *name* refers to an existing index."""
        return name in self._indexes

    # ------------------------------------------------------------------
    # Document operations
    # ------------------------------------------------------------------

    async def index_document(
        self,
        index_name: str,
        document_id: str,
        document: dict[str, Any],
    ) -> None:
        """Index a single document.

        Args:
            index_name: Target index (created on demand).
            document_id: Unique document identifier within the index.
            document: Document payload.
        """
        self._indexes.setdefault(index_name, {})[str(document_id)] = dict(document)

    async def index_many(
        self,
        index_name: str,
        documents: list[dict[str, Any]],
    ) -> int:
        """Index multiple documents.

        Args:
            index_name: Target index (created on demand).
            documents: Sequence of ``{"id": ..., "document": {...}}`` mappings.

        Returns:
            Number of documents indexed.
        """
        store = self._indexes.setdefault(index_name, {})
        count = 0
        for item in documents:
            store[str(item["id"])] = dict(item["document"])
            count += 1
        return count

    async def delete_document(self, index_name: str, document_id: str) -> None:
        """Delete a document from an index.

        Args:
            index_name: Target index (unknown names are ignored).
            document_id: Document identifier to remove.
        """
        store = self._indexes.get(index_name)
        if store is not None:
            store.pop(str(document_id), None)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(self, index_name: str, query: Any, **kwargs: Any) -> SearchResults:
        """Search an index.

        Args:
            index_name: Index to search.
            query: Query string, or a mapping such as
                ``{"query": "..."}`` — the first string value found is
                used as the search term.
            **kwargs: Ignored; present for protocol compatibility.

        Returns:
            :class:`SearchResults` with matching documents in ``hits``.
        """
        store = self._indexes.get(index_name, {})
        term = self._extract_term(query)
        hits: list[dict[str, Any]] = []
        for document_id, document in store.items():
            haystack = f"{document_id} {document}".lower()
            if term.lower() in haystack:
                hits.append({"id": document_id, "document": dict(document)})
        return SearchResults(hits=hits, total=len(hits))

    @staticmethod
    def _extract_term(query: Any) -> str:
        """Reduce a query string or mapping to a single search term."""
        if isinstance(query, str):
            return query
        if isinstance(query, dict):
            for value in query.values():
                if isinstance(value, str):
                    return value
        return str(query)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Return a healthy :class:`HealthCheckResult`.

        Args:
            timeout: Ignored; present for protocol compatibility.
        """
        return HealthCheckResult(
            component="in-memory-search",
            status=HealthStatus.HEALTHY,
            message="in-memory search engine available",
        )
