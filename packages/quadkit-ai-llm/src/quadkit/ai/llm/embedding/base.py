"""Base classes and interfaces for embedding providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from quadkit.ai.llm.embedding.config import EmbeddingConfig
from quadkit.contracts.core.health import HealthCheckResult, HealthStatus


@dataclass
class EmbeddingModelInfo:
    """Metadata about an embedding model.

    Attributes:
        model_id: Unique model identifier
        provider: Provider name
        display_name: Human-readable name
        embedding_dimension: Output embedding dimension
        max_input_tokens: Maximum input tokens
        max_batch_size: Maximum tokens per batch request
        input_cost_per_million: Cost per 1M input tokens
    """

    model_id: str
    provider: str
    display_name: str
    embedding_dimension: int
    max_input_tokens: int = 8192
    max_batch_size: int = 100
    input_cost_per_million: float = 0.0

    @property
    def cost_per_million_tokens(self) -> float:
        """Alias for input_cost_per_million."""
        return self.input_cost_per_million


class AbstractEmbeddingAdapter(ABC):
    """Base class for embedding provider adapters.

    All embedding adapters implement this interface to provide a unified
    API for different embedding models.
    """

    def __init__(self, config: EmbeddingConfig) -> None:
        """Initialize embedding adapter.

        Args:
            config: Provider configuration with model, batch size, and timeout.
        """
        self._config = config

    @abstractmethod
    async def embed(
        self,
        texts: str | list[str],
        *,
        model: str | None = None,
        batch_size: int = 100,
    ) -> list[list[float]]:
        """Generate embeddings for text(s).

        Args:
            texts: Single text string or list of texts
            model: Optional model override
            batch_size: Batch size for processing

        Returns:
            List of embedding vectors (one per input text)

        Raises:
            EmbeddingError: If embedding generation fails
        """
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check embedding service connectivity.

        Args:
            timeout: Maximum seconds to wait for the health check.

        Returns:
            HealthCheckResult indicating HEALTHY or UNHEALTHY status.
        """
        component = f"embedding_{self._config.model}"
        try:
            await self.embed(["health check"])
            return HealthCheckResult(component=component, status=HealthStatus.HEALTHY)
        except Exception as exc:  # noqa: BLE001
            return HealthCheckResult(
                component=component,
                status=HealthStatus.UNHEALTHY,
                message=f"Embedding health check failed ({type(exc).__name__})",
            )

    @abstractmethod
    def get_models(self) -> list[EmbeddingModelInfo]:
        """Get available embedding models for this provider.

        Returns:
            List of available model information
        """
        ...

    async def close(self) -> None:
        """Clean up resources."""


__all__ = [
    "AbstractEmbeddingAdapter",
    "EmbeddingModelInfo",
]
