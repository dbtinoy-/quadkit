"""RAG pipeline, retrieval, and reranking protocols."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from quadkit.contracts.ai.exceptions import RAGError

if TYPE_CHECKING:
    from quadkit.contracts.ai.vector import DocumentProtocol, SearchResultProtocol
    from quadkit.contracts.core.result import Result


# RAG Errors
class RetrievalError(RAGError):
    """Error raised during document retrieval."""

    _code = "QK_ERR_RAG_002"


class SynthesisError(RAGError):
    """Error raised during response synthesis."""

    _code = "QK_ERR_RAG_003"


class ChunkingError(RAGError):
    """Error raised during document chunking."""

    _code = "QK_ERR_RAG_004"


@runtime_checkable
class ChunkProtocol(Protocol):
    """Structural protocol for document chunks."""

    @property
    def text(self) -> str:
        """Chunk text content."""
        ...

    @property
    def metadata(self) -> dict[str, Any]:
        """Chunk metadata."""
        ...

    @property
    def score(self) -> float | None:
        """Optional relevance score."""
        ...


@dataclass(frozen=True)
class RAGContext:
    """Inputs to a RAG pipeline."""

    query: str
    config: dict[str, Any] | None = None
    filters: dict[str, Any] | None = None
    session_id: str | None = None


@dataclass(frozen=True)
class RAGResponse:
    """Outputs from a RAG pipeline."""

    answer: str
    sources: list[SearchResultProtocol]
    citations: list[Any] | None = None
    confidence: float | None = None


@runtime_checkable
class DocumentLoaderProtocol(Protocol):
    """Protocol for loading documents."""

    async def load(self, source: str, **kwargs: Any) -> list[DocumentProtocol]:
        """Load documents from a source."""
        ...


@runtime_checkable
class SynthesizerProtocol(Protocol):
    """Protocol for synthesizing a final answer from context."""

    async def synthesize(
        self,
        query: str,
        context: list[SearchResultProtocol],
        **kwargs: Any,
    ) -> Result[RAGResponse, RAGError]:
        """Synthesize retrieved documents into an answer."""
        ...


@runtime_checkable
class RAGPipelineProtocol(Protocol):
    """Protocol for RAG pipeline execution.

    Orchestrates retrieval, synthesis, and quality stages for a
    given query context.
    """

    async def execute(self, context: RAGContext) -> Result[RAGResponse, RAGError]:
        """Execute the full RAG pipeline for the given context.

        Args:
            context: Pipeline context containing query and config.

        Returns:
            Updated context with retrieved and synthesised response.
        """
        ...


@runtime_checkable
class RetrievalStrategyProtocol(Protocol):
    """Protocol for pluggable RAG retrieval and ranking strategies.

    Implementations take a query and a set of candidate documents and
    return an ordered subset.
    """

    async def retrieve(
        self,
        query: str,
        candidates: list[SearchResultProtocol],
        *,
        top_k: int = 5,
        **kwargs: Any,
    ) -> list[SearchResultProtocol]:
        """Rank and return the top-k most relevant candidates.

        Args:
            query: Query string.
            candidates: Retrieved candidate documents.
            top_k: Maximum number of results to return.
            **kwargs: Strategy-specific options.

        Returns:
            Ordered list of the most relevant documents.
        """
        ...


@runtime_checkable
class RerankingStrategyProtocol(Protocol):
    """Protocol for cross-encoder or LLM-based reranking strategies.

    Applied after initial retrieval to reorder documents by relevance.
    """

    async def rerank(
        self,
        query: str,
        documents: list[SearchResultProtocol],
        *,
        top_k: int | None = None,
    ) -> list[SearchResultProtocol]:
        """Reorder documents by relevance to query.

        Args:
            query: Query string.
            documents: Documents to rerank.
            top_k: If set, return only the top-k results.

        Returns:
            Reranked (and optionally truncated) list of documents.
        """
        ...


@runtime_checkable
class RAGEvaluatorProtocol(Protocol):
    """Protocol for evaluating RAG pipeline quality.

    Implementations run metrics (faithfulness, relevance, etc.) on a
    completed RAG interaction and return a structured report.
    """

    async def evaluate(
        self,
        query: str,
        retrieved_docs: list[Any],
        generated_answer: str,
        **kwargs: Any,
    ) -> Any:
        """Evaluate a completed RAG interaction.

        Args:
            query: The original user query.
            retrieved_docs: Documents retrieved by the pipeline.
            generated_answer: The synthesized answer produced by the pipeline.
            **kwargs: Additional evaluation parameters.

        Returns:
            An evaluation report (``RAGEvaluationReport`` or similar).
        """
        ...


@runtime_checkable
class PromptCompressorProtocol(Protocol):
    """Compresses text to fit within a token budget.

    Implementations range from learned compression (LLMLingua-2) to
    heuristic truncation. The protocol guarantees that the returned text
    fits within target_token_count.

    Placement note: Lives in ai/rag.py because its primary consumer is the
    RAG context compression stage. Also consumed by the optional provider.
    """

    async def compress(
        self,
        text: str,
        target_token_count: int,
        force_tokens: list[str] | None = None,
    ) -> str:
        """Compress text to fit within target_token_count.

        Args:
            text: The raw text to compress.
            target_token_count: Maximum tokens in the result.
            force_tokens: Tokens that must never be removed.

        Returns:
            Compressed text fitting within the budget.
        """
        ...


__all__ = [
    "ChunkProtocol",
    "ChunkingError",
    "DocumentLoaderProtocol",
    "PromptCompressorProtocol",
    "RAGContext",
    "RAGError",
    "RAGEvaluatorProtocol",
    "RAGPipelineProtocol",
    "RAGResponse",
    "RerankingStrategyProtocol",
    "RetrievalError",
    "RetrievalStrategyProtocol",
    "SynthesisError",
    "SynthesizerProtocol",
]
