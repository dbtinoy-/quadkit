"""Index and query engine protocols for RAG."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.ai.vector import Document
    from quadkit.contracts.core.result import Result

from quadkit.contracts.ai.exceptions import RAGError


class IndexError(RAGError):  # noqa: A001
    """Raised when index operations fail in an expected, recoverable way."""

    _code = "QK_ERR_IDX_001"

    def __init__(self, message: str = "Index error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


class QueryEngineError(RAGError):
    """Raised when query engine operations fail in an expected, recoverable way."""

    _code = "QK_ERR_QE_001"

    def __init__(self, message: str = "Query engine error", **kwargs: Any) -> None:
        super().__init__(message, **kwargs)


@dataclass(frozen=True)
class Citation:
    """A citation linking an answer fragment to a source node.

    Attributes:
        node_id: Unique identifier of the source node.
        text: The cited text content.
        score: Relevance score of the citation.
    """

    node_id: str
    text: str
    score: float


@dataclass(frozen=True)
class QueryEngineResponse:
    """Response from a query engine.

    Attributes:
        answer: The generated answer text.
        source_nodes: List of source nodes used in generation.
        citations: List of citations linking answer to sources.
        tokens: Total tokens used (if available, otherwise 0).
        cost: Total cost in USD (if available, otherwise 0.0).
    """

    answer: str
    source_nodes: list[Any] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    tokens: int = 0
    cost: float = 0.0


@runtime_checkable
class IndexProtocol(Protocol):
    """Protocol for document indices.

    Implementations store embedded documents and provide search capabilities.
    """

    async def insert(self, documents: list[Document]) -> Result[list[str], IndexError]:
        """Insert documents into the index.

        Args:
            documents: List of documents to insert.

        Returns:
            Ok(list of document IDs) on success.
            Err(IndexError) on failure.
        """
        ...

    async def delete(self, ids: list[str]) -> Result[int, IndexError]:
        """Delete documents by ID.

        Args:
            ids: List of document IDs to delete.

        Returns:
            Ok(count of deleted documents) on success.
            Err(IndexError) on failure.
        """
        ...

    def as_retriever(self, **kwargs: Any) -> Any:
        """Convert this index to a retriever.

        Args:
            **kwargs: Retriever-specific parameters (top_k, filters, etc.).

        Returns:
            A retriever instance.
        """
        ...


@runtime_checkable
class QueryEngineProtocol(Protocol):
    """Protocol for query engines.

    Implementations process user queries and return answers with sources.
    """

    async def query(
        self, query: str, **kwargs: Any
    ) -> Result[QueryEngineResponse, QueryEngineError]:
        """Process a query and return an answer with sources.

        Args:
            query: The user's query string.
            **kwargs: Query-specific parameters.

        Returns:
            Ok(QueryEngineResponse) on success.
            Err(QueryEngineError) on failure.
        """
        ...

    async def astream_query(
        self, query: str, **kwargs: Any
    ) -> AsyncIterator[Result[QueryEngineResponse, QueryEngineError]]:
        """Stream query results.

        Args:
            query: The user's query string.
            **kwargs: Query-specific parameters.

        Yields:
            Result containing partial QueryEngineResponse or error.
        """
        ...


__all__ = [
    "Citation",
    "IndexError",
    "IndexProtocol",
    "QueryEngineError",
    "QueryEngineProtocol",
    "QueryEngineResponse",
]
