"""Provider registry contracts for multi-provider LLM selection and fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from typing_extensions import Protocol, runtime_checkable

from quadkit.contracts.ai.types import ModelCapability

if TYPE_CHECKING:
    from quadkit.contracts.ai.llm import LLMClientProtocol


class SelectionStrategy(StrEnum):
    """Strategy for selecting which model/provider to use.

    Attributes:
        COST_OPTIMAL: Choose cheapest option that meets requirements
        LATENCY_OPTIMAL: Choose fastest provider
        CAPABILITY_MATCH: Choose first model supporting all required capabilities
        ROUND_ROBIN: Rotate through healthy providers
        PREFERRED: Try preferred provider, fallback to others
    """

    COST_OPTIMAL = "cost_optimal"
    LATENCY_OPTIMAL = "latency_optimal"
    CAPABILITY_MATCH = "capability_match"
    ROUND_ROBIN = "round_robin"
    PREFERRED = "preferred"


@dataclass(frozen=True)
class ModelInfo:
    """Information about an available LLM model.

    Attributes:
        model_id: Unique model identifier (e.g., "gpt-4o")
        provider: Provider name (e.g., "openai")
        display_name: Human-readable name
        capabilities: Set of capabilities this model has
        context_window: Input context window size in tokens
        max_output_tokens: Maximum output tokens this model can generate
        input_cost_per_million: Cost per million input tokens (USD)
        output_cost_per_million: Cost per million output tokens (USD)
        is_available: Whether model is currently available
        metadata: Additional provider-specific metadata
    """

    model_id: str
    provider: str
    display_name: str
    capabilities: frozenset[ModelCapability]
    context_window: int
    max_output_tokens: int
    input_cost_per_million: float
    output_cost_per_million: float
    is_available: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderHealth:
    """Health status of a provider.

    Mutable dataclass tracking provider health metrics including
    latency, error rate, and availability status.

    Attributes:
        provider: Provider name
        is_healthy: Whether provider is considered healthy
        latency_ms: Average response latency in milliseconds
        error_rate: Error rate as a fraction (0-1)
        last_check: When health was last checked
        details: Additional health detail information
    """

    provider: str
    is_healthy: bool
    latency_ms: float
    error_rate: float
    last_check: datetime
    details: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class ProviderRegistryProtocol(Protocol):
    """Protocol for registering and discovering LLM providers.

    Maintains a registry of supported providers and their models,
    with health tracking and capability-based filtering.
    """

    async def register_provider(
        self, name: str, client: LLMClientProtocol, models: list[ModelInfo]
    ) -> None:
        """Register a new provider with its available models.

        Args:
            name: Provider name (e.g., "openai", "anthropic")
            client: The LLM client for this provider
            models: List of available models from this provider
        """
        ...

    async def get_client(self, provider: str) -> LLMClientProtocol | None:
        """Get the LLM client for a provider.

        Args:
            provider: Provider name

        Returns:
            The LLM client, or None if not registered
        """
        ...

    def list_providers(self) -> list[str]:
        """List all registered provider names.

        Returns:
            List of provider names
        """
        ...

    def list_models(
        self, capabilities: set[ModelCapability] | None = None
    ) -> list[ModelInfo]:
        """List all available models with optional capability filtering.

        Args:
            capabilities: If provided, return only models with all these capabilities

        Returns:
            List of model information
        """
        ...

    def get_model_info(self, model_id: str) -> ModelInfo | None:
        """Get information about a specific model.

        Args:
            model_id: The model identifier

        Returns:
            Model information, or None if not found
        """
        ...


@runtime_checkable
class ModelSelectorProtocol(Protocol):
    """Protocol for selecting models based on criteria.

    Implements various selection strategies including cost optimization,
    latency optimization, and capability matching.
    """

    async def select(
        self,
        capabilities: set[ModelCapability],
        preferred_provider: str | None = None,
        max_cost_per_million: float | None = None,
        strategy: SelectionStrategy = SelectionStrategy.COST_OPTIMAL,
    ) -> ModelInfo | None:
        """Select a model based on the given criteria.

        Args:
            capabilities: Required capabilities for the model
            preferred_provider: Prefer this provider if possible
            max_cost_per_million: Maximum cost threshold (if relevant to strategy)
            strategy: Selection strategy to use

        Returns:
            Selected model info, or None if no suitable model found
        """
        ...


@runtime_checkable
class FallbackChainProtocol(Protocol):
    """Protocol for executing requests with provider fallback.

    Handles cascading requests across multiple providers with
    automatic fallback on failure.
    """

    async def execute(self, request: Any, providers: list[str]) -> Any:
        """Execute request with automatic fallback to other providers.

        Tries providers in order until one succeeds.

        Args:
            request: The request to execute
            providers: List of provider names to try in order

        Returns:
            The response from the first successful provider

        Raises:
            AllProvidersExhaustedError: If all providers failed
        """
        ...


__all__ = [
    "FallbackChainProtocol",
    "ModelInfo",
    "ModelSelectorProtocol",
    "ProviderHealth",
    "ProviderRegistryProtocol",
    "SelectionStrategy",
]
