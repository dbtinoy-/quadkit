"""Vector store and document protocols."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.core import HealthCheckResult
    from quadkit.contracts.core.result import Result
    from quadkit.contracts.data.vector.exceptions import VectorError


@runtime_checkable
class DocumentProtocol(Protocol):
    """Structural protocol for unified document representation.

    Structural protocol satisfied by any class with the required
    fields — used across quadkit-vector and quadkit-ai-rag.
    """

    @property
    def id(self) -> str | None:
        """Unique document identifier, or None if unassigned."""
        ...

    @property
    def text(self) -> str:
        """Text content of the document."""
        ...

    @property
    def metadata(self) -> dict[str, Any]:
        """Arbitrary metadata key-value pairs."""
        ...


@dataclass(frozen=True)
class EmbeddingResult:
    """Result of an embedding operation."""

    vectors: list[list[float]]
    model: str
    tokens: int


@runtime_checkable
class SearchResultProtocol(Protocol):
    """Protocol for a vector search hit."""

    @property
    def text(self) -> str:
        """The text content of the search result."""
        ...

    @property
    def document(self) -> DocumentProtocol:
        """The retrieved document."""
        ...

    @property
    def score(self) -> float:
        """Relevance score."""
        ...

    @property
    def metadata(self) -> dict[str, Any]:
        """Additional search-specific metadata."""
        ...


@runtime_checkable
class BatchProcessorProtocol(Protocol):
    """Protocol for batch operations on documents."""

    async def process_batch(
        self,
        documents: list[DocumentProtocol],
        **kwargs: Any,
    ) -> Result[int, VectorError]:
        """Process a batch of documents."""
        ...


@runtime_checkable
class DocumentVectorStoreProtocol(Protocol):
    """Document-centric vector store API for RAG and AI packages.

    This is the AI-layer contract for add/search/delete against embedded
    documents. For connection lifecycle and collection management, use
    :class:`~quadkit.contracts.data.vector.protocols.VectorStoreProtocol`
    (infrastructure layer).

    All vector database drivers (Qdrant, ChromaDB, PGVector, etc.) are adapted
    to this shape via ``quadkit-vector`` so callers can swap backends.
    """

    async def add(
        self, documents: list[DocumentProtocol]
    ) -> Result[list[str], VectorError]:
        """Add documents to the vector store.

        Args:
            documents: List of documents with text and metadata.

        Returns:
            ``Ok(list[str])`` with document IDs on success, or
            ``Err(VectorStoreError)`` on failure.
        """
        ...

    async def batch_upsert(
        self,
        documents: list[DocumentProtocol],
        batch_size: int = 100,
    ) -> Result[int, VectorError]:
        """Upsert documents in batches.

        Args:
            documents: List of documents to upsert.
            batch_size: Number of documents per batch. defaults to 100.

        Returns:
            ``Ok(int)`` with the total count of documents upserted, or
            ``Err(VectorStoreError)`` on failure.
        """
        ...

    async def search(
        self,
        query: list[float],
        *,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
        score_threshold: float | None = None,
    ) -> Result[list[SearchResultProtocol], VectorError]:
        """Search for similar documents using a vector.

        Args:
            query: Query embedding vector.
            top_k: Number of results to return.
            filters: Metadata filters.
            score_threshold: Minimum relevance score.

        Returns:
            ``Ok(list of search results)`` on success, or
            ``Err(VectorStoreError)`` on failure.
        """
        ...

    async def search_text(
        self,
        query: str,
        *,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> Result[list[SearchResultProtocol], VectorError]:
        """Search for similar documents using text.

        Args:
            query: Query text.
            top_k: Number of results to return.
            filters: Metadata filters.

        Returns:
            ``Ok(list of search results)`` on success, or
            ``Err(VectorStoreError)`` on failure.
        """
        ...

    async def delete(self, ids: list[str]) -> Result[int, VectorError]:
        """Delete documents by ID.

        Args:
            ids: List of document IDs to delete.

        Returns:
            ``Ok(int)`` with the count of deleted documents on success, or
            ``Err(VectorStoreError)`` on failure.
        """
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Perform a lightweight connectivity check.

        Returns:
            Structured health check result.
        """
        ...


@runtime_checkable
class ChunkerProtocol(Protocol):
    """Protocol for document chunking strategies.

    Implementations split document text into smaller, overlapping
    or non-overlapping chunks suitable for embedding and retrieval.
    """

    def chunk(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[Any]:
        """Split text into chunks.

        Args:
            text: The document text to chunk.
            metadata: Optional metadata to attach to each chunk.

        Returns:
            List of Chunk objects.
        """
        ...


@dataclass(frozen=True)
class Document:
    """Concrete document data class shared across AI packages.

    Satisfies ``DocumentProtocol``.  Use this when constructing documents
    in packages that must not depend on ``quadkit-vector``.
    """

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str | None = None
    embedding: list[float] | None = None


@dataclass(frozen=True)
class RAGSearchResult:
    """Enriched search result for RAG applications.

    Unlike the generic SearchResult from the storage layer (data/vector/types.py),
    this result is focused on RAG workflows:
    - Wraps a full Document object (not just id/score/vector/content)
    - Includes ranking information useful for re-ranking pipelines
    - Immutable value object; post-processing produces a new instance

    Satisfies ``SearchResultProtocol``.
    """

    document: Document
    score: float
    rank: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Text content of the wrapped document."""
        return self.document.text


__all__ = [
    "BatchProcessorProtocol",
    "ChunkerProtocol",
    "Document",
    "DocumentProtocol",
    "DocumentVectorStoreProtocol",
    "EmbeddingResult",
    "RAGSearchResult",
    "SearchResultProtocol",
]
