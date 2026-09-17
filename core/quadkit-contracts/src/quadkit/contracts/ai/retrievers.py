"""Retriever protocols and value objects for Quadkit.

Defines contracts for document retrieval and node postprocessing,
analogous to LangChain's retriever interfaces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.core.result import Result

from quadkit.contracts.ai.exceptions import RetrieverError

__all__ = [
    "NodePostprocessorProtocol",
    "RetrievalQuery",
    "RetrievedNode",
    "RetrieverError",
    "RetrieverProtocol",
]


@dataclass(frozen=True)
class RetrievalQuery:
    """Query parameters for document retrieval.

    Attributes:
        query: The search query text.
        top_k: Number of results to return.
    """

    query: str
    top_k: int = 10


@dataclass(frozen=True)
class RetrievedNode:
    """A single retrieved document node.

    Attributes:
        id: Unique identifier for the node.
        content: Text content of the node.
        score: Relevance score (typically 0-1).
        metadata: Optional metadata dictionary.
    """

    id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class RetrieverProtocol(Protocol):
    """Protocol for document retrieval.

    Implementations provide async retrieval of relevant documents
    based on a query string.
    """

    async def retrieve(
        self, query: str, top_k: int = 10
    ) -> Result[list[RetrievedNode], RetrieverError]:
        """Retrieve relevant documents for a query.

        Args:
            query: The search query text.
            top_k: Number of results to return.

        Returns:
            Ok(list of RetrievedNode) on success.
            Err(RetrieverError) on failure.
        """
        ...


@runtime_checkable
class NodePostprocessorProtocol(Protocol):
    """Protocol for postprocessing retrieved nodes.

    Implementations transform, filter, or enrich retrieved nodes
    after initial retrieval.
    """

    async def postprocess(
        self, nodes: list[RetrievedNode]
    ) -> Result[list[RetrievedNode], RetrieverError]:
        """Postprocess retrieved nodes.

        Args:
            nodes: List of retrieved nodes to process.

        Returns:
            Ok(list of processed RetrievedNode) on success.
            Err(RetrieverError) on failure.
        """
        ...
