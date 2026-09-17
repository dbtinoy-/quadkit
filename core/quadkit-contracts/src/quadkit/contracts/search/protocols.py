"""Search protocol definitions.

Protocols for search engines, index management, searchable entities,
and search analytics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.core import HealthCheckResult


@runtime_checkable
class SearchEngineProtocol(Protocol):
    """Protocol for search engine backends.

    All operations are **index-scoped**: the target index name is the
    first argument of every method. This matches the shape implemented by
    every concrete backend (Meilisearch, Elasticsearch, SQLite FTS,
    PostgreSQL FTS, MySQL FTS) and by the
    :class:`~the optional provider module` facade,
    which delegates to backends using these signatures.

    (The previous revision declared a single-index shape with optional
    ``index_name`` kwargs; the concrete backends never matched it.)
    """

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
        """Execute a search query against *index*.

        Args:
            index: Target index name.
            query: Search query string.
            filters: Search filters (backend-specific structure).
            limit: Maximum results to return.
            offset: Results offset for pagination.
            sort: Sort terms, ``"field:asc|desc"`` strings.
            **kwargs: Backend-specific options (e.g. ``rule``).

        Returns:
            ``Ok(SearchResponse)`` on success, ``Err(SearchError)`` on
            failure — the canonical
            :class:`~quadkit.result.Result` type.
        """
        ...

    async def index_document(
        self,
        index: str,
        document_id: str,
        document: dict[str, Any],
        **kwargs: Any,
    ) -> Any:
        """Index a document.

        Args:
            index: Target index name.
            document_id: Unique document identifier.
            document: Document data to index.
            **kwargs: Backend-specific options.
        """
        ...

    async def index_many(
        self,
        index: str,
        documents: list[tuple[str, dict[str, Any]]],
        **kwargs: Any,
    ) -> Any:
        """Index multiple documents in a single bulk operation.

        Callers should prefer this over N repeated :meth:`index_document`
        calls when processing batches. Backends may use a native bulk API
        to avoid per-document round-trip overhead.

        Args:
            index: Target index name.
            documents: Sequence of ``(document_id, document)`` pairs.
            **kwargs: Backend-specific options.
        """
        ...

    async def get_document(
        self,
        index: str,
        document_id: str,
        **kwargs: Any,
    ) -> dict[str, Any] | None:
        """Retrieve a document by ID, or ``None`` when absent.

        Args:
            index: Target index name.
            document_id: Document identifier to retrieve.
            **kwargs: Backend-specific options.
        """
        ...

    async def delete_document(
        self,
        index: str,
        document_id: str,
        **kwargs: Any,
    ) -> Any:
        """Delete a document from the index.

        Args:
            index: Target index name.
            document_id: Document identifier to delete.
            **kwargs: Backend-specific options.
        """
        ...

    async def create_index(self, index: str, **kwargs: Any) -> Any:
        """Create the index (and schema) if it does not exist."""
        ...

    async def delete_index(self, index: str, **kwargs: Any) -> Any:
        """Delete the index and all its documents."""
        ...

    async def index_exists(self, index: str, **kwargs: Any) -> Any:
        """Check whether the index exists."""
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform health check.

        Returns:
            Structured health check result.
        """
        ...


@runtime_checkable
class IndexManagerProtocol(Protocol):
    """Protocol for managing search indices."""

    async def create_index(
        self,
        index_name: str,
        schema: dict[str, Any],
    ) -> None:
        """Create a search index.

        Args:
            index_name: Name of the index to create
            schema: Index schema definition
        """
        ...

    async def delete_index(self, index_name: str) -> None:
        """Delete a search index.

        Args:
            index_name: Name of the index to delete
        """
        ...

    async def get_index_info(self, index_name: str) -> dict[str, Any]:
        """Get information about an index.

        Args:
            index_name: Name of the index

        Returns:
            Index information
        """
        ...

    async def index_exists(self, index_name: str) -> bool:
        """Check whether an index exists.

        Args:
            index_name: Name of the index to check.

        Returns:
            ``True`` if the index exists, ``False`` otherwise.
        """
        ...


@runtime_checkable
class SearchableProtocol(Protocol):
    """Protocol for entities that can be searched."""

    @property
    def search_document_id(self) -> str:
        """Unique identifier for search indexing."""
        ...

    @property
    def search_document(self) -> dict[str, Any]:
        """Document representation for search indexing."""
        ...

    @property
    def search_index_name(self) -> str:
        """Name of the search index for this entity."""
        ...


@runtime_checkable
class SearchAnalyticsProtocol(Protocol):
    """Protocol for search analytics and metrics."""

    async def record_search(
        self,
        query: str,
        filters: dict[str, Any] | None,
        result_count: int,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Record a search query for analytics.

        Args:
            query: Search query string
            filters: Applied filters
            result_count: Number of results returned
            user_id: User identifier (optional)
            session_id: Session identifier (optional)
        """
        ...

    async def get_search_metrics(
        self,
        time_range: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Get search analytics metrics.

        Args:
            time_range: Time range for metrics (optional)

        Returns:
            Search metrics data
        """
        ...


@runtime_checkable
class DatabaseSearchBackendProtocol(Protocol):
    """Protocol for database-backed search backends."""

    async def connect(self) -> None:
        """Establish connection to the database."""
        ...

    async def close(self) -> None:
        """Close the database connection."""
        ...

    async def ensure_schema(self, index_name: str) -> None:
        """Ensure the search schema/tables exist for an index."""
        ...


@runtime_checkable
class DocumentTransformerProtocol(Protocol):
    """Protocol for transforming documents for search indexing.

    Transforms domain models into search-indexable documents with
    appropriate text extraction, field mapping, and metadata.

    Example:
        ```python
        class MyDocumentTransformer:
            def transform(self, entity: MyEntity) -> dict[str, Any]:
                return {
                    "id": entity.id,
                    "title": entity.name,
                    "content": self._extract_text(entity.description),
                    "metadata": {"created_at": entity.created_at.isoformat()}
                }
        ```
    """

    def transform(self, entity: Any) -> dict[str, Any]:
        """Transform a domain entity to a search document.

        Args:
            entity: Domain entity to transform.

        Returns:
            Search-indexable document dictionary.
        """
        ...

    def transform_batch(self, entities: list[Any]) -> list[dict[str, Any]]:
        """Transform multiple domain entities to search documents.

        Args:
            entities: Domain entities to transform.

        Returns:
            List of search-indexable document dictionaries.
        """
        ...

    def extract_text(self, content: Any) -> str:
        """Extract searchable text from content.

        Args:
            content: Content to extract text from.

        Returns:
            Extracted text string.
        """
        ...


__all__ = [
    "DatabaseSearchBackendProtocol",
    "DocumentTransformerProtocol",
    "IndexManagerProtocol",
    "SearchAnalyticsProtocol",
    "SearchEngineProtocol",
    "SearchableProtocol",
]
