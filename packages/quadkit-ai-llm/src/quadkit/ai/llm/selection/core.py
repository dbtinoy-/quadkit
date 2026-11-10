"""Model selection and routing for intelligent LLM usage.

This module provides intelligent model selection based on task characteristics,
allowing you to optimize for cost, quality, and latency.

Example:
    >>> from quadkit.ai.llm import ModelSelector, SelectionStrategy
    >>>
    >>> selector = ModelSelector(
    ...     default_model="gpt-3.5-turbo",
    ...     strategies=[
    ...         SelectionStrategy(
    ...             name="complex",
    ...             model="gpt-4-turbo",
    ...             conditions={"min_tokens": 1000}
    ...         )
    ...     ],
    ...     fallback_chain=["gpt-4-turbo", "gpt-3.5-turbo", "ollama/llama3"]
    ... )
    >>>
    >>> # Automatically selects appropriate model
    >>> model = selector.select("Write a complex analysis...")
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from quadkit.ai.llm.selection._capabilities import (
    DEFAULT_MODEL_CAPABILITIES,
    ModelCapabilities,
)
from quadkit.contracts.ai.llm import TokenCounterProtocol
from quadkit.domain import DomainModel
from quadkit.validation import Field

__all__ = [
    "DEFAULT_MODEL_CAPABILITIES",
    "ModelCapabilities",
    "ModelSelector",
    "SelectionCriteria",
    "SelectionStrategy",
    "create_balanced_selector",
    "create_cost_optimized_selector",
    "create_quality_optimized_selector",
]


class SelectionCriteria(StrEnum):
    """Criteria for model selection."""

    TOKEN_COUNT = "token_count"  # noqa: S105  # criterion name, not a credential
    COST = "cost"
    LATENCY = "latency"
    QUALITY = "quality"
    CUSTOM = "custom"


@dataclass(init=False)
class SelectionStrategy(DomainModel):
    """Strategy for selecting models based on conditions.

    Example:
        >>> strategy = SelectionStrategy(
        ...     name="long_context",
        ...     model="gpt-4-turbo-preview",
        ...     conditions={
        ...         "min_tokens": 2000,
        ...         "max_tokens": 100000
        ...     }
        ... )
    """

    name: str = Field(..., description="Strategy name")
    model: str = Field(..., description="Model to use for this strategy")
    conditions: dict[str, Any] = Field(
        default_factory=dict,
        description="Conditions that trigger this strategy",
    )
    priority: int = Field(
        default=0,
        description="Priority (higher = evaluated first)",
    )
    description: str | None = Field(
        None,
        description="Human-readable description",
    )

    def matches(self, context: dict[str, Any]) -> bool:
        """Check if this strategy matches the given context.

        Args:
            context: Context dictionary with prompt info

        Returns:
            True if all conditions are met

        Example:
            >>> context = {"token_count": 2500, "has_code": True}
            >>> strategy.matches(context)
            True
        """
        for key, value in self.conditions.items():
            # Handle different condition types
            if key.startswith("min_"):
                actual_key = key[4:]  # Remove "min_" prefix
                if actual_key not in context:
                    return False
                if context[actual_key] < value:
                    return False
            elif key.startswith("max_"):
                actual_key = key[4:]  # Remove "max_" prefix
                if actual_key not in context:
                    return False
                if context[actual_key] > value:
                    return False
            elif key.startswith("has_"):
                # Boolean flag check
                if key not in context:
                    return False
                if context[key] != value:
                    return False
            else:
                # Exact match
                if key not in context:
                    return False
                if context[key] != value:
                    return False

        return True


class ModelSelector:
    """Intelligent model selector with fallback support.

    Automatically selects the best model based on prompt characteristics
    and provides fallback chains for reliability.

    Example:
        >>> selector = ModelSelector(
        ...     default_model="gpt-3.5-turbo",
        ...     strategies=[
        ...         SelectionStrategy(
        ...             name="complex",
        ...             model="gpt-4-turbo",
        ...             conditions={"min_tokens": 1000}
        ...         ),
        ...         SelectionStrategy(
        ...             name="simple",
        ...             model="claude-3-haiku-20240307",
        ...             conditions={"max_tokens": 500}
        ...         )
        ...     ],
        ...     fallback_chain=["gpt-4-turbo", "gpt-3.5-turbo"]
        ... )
        >>>
        >>> # Select model for a prompt
        >>> model = selector.select("Long prompt here...")
        >>> print(model)
        'gpt-4-turbo'
        >>>
        >>> # Get next fallback on error
        >>> fallback = selector.get_fallback("gpt-4-turbo")
        >>> print(fallback)
        'gpt-3.5-turbo'
    """

    def __init__(
        self,
        default_model: str | None = None,
        strategies: list[SelectionStrategy] | None = None,
        fallback_chain: list[str] | None = None,
        model_capabilities: dict[str, ModelCapabilities] | None = None,
        token_counter: TokenCounterProtocol | None = None,
    ):
        """Initialize model selector.

        Args:
            default_model: Default model to use
            strategies: List of selection strategies
            fallback_chain: Ordered list of fallback models
            model_capabilities: Custom model capabilities
            token_counter: Token counter for prompt analysis

        Example:
            >>> selector = ModelSelector(
            ...     default_model="gpt-3.5-turbo",
            ...     fallback_chain=["gpt-4", "claude-3-sonnet-20240229"]
            ... )
        """
        if default_model is None:
            default_model = "gpt-3.5-turbo"

        self.default_model = default_model
        self.strategies = sorted(
            strategies or [],
            key=lambda s: s.priority,
            reverse=True,
        )
        self.fallback_chain = fallback_chain or [default_model]
        self.model_capabilities = model_capabilities or DEFAULT_MODEL_CAPABILITIES
        self.token_counter = token_counter

    def select(
        self,
        prompt: str,
        context: dict[str, Any] | None = None,
        required_capabilities: list[str] | None = None,
    ) -> str:
        """Select the best model for the given prompt.

        Args:
            prompt: The prompt text
            context: Additional context for selection
            required_capabilities: Required capabilities (e.g., ["supports_functions"])

        Returns:
            Selected model name

        Example:
            >>> model = selector.select(
            ...     "Analyze this image...",
            ...     required_capabilities=["supports_vision"]
            ... )
            >>> print(model)
            'gpt-4-turbo'
        """
        # Build context
        ctx = self._build_context(prompt, context or {})

        # Filter by required capabilities
        available_models = self._filter_by_capabilities(required_capabilities)

        # Try each strategy in priority order
        for strategy in self.strategies:
            if strategy.model not in available_models:
                continue

            if strategy.matches(ctx):
                return strategy.model

        # Return default if no strategy matched
        return (
            self.default_model
            if self.default_model in available_models
            else available_models[0]
        )

    def get_fallback(self, failed_model: str) -> str | None:
        """Get the next model in the fallback chain.

        Args:
            failed_model: The model that failed

        Returns:
            Next fallback model, or None if no fallback available

        Example:
            >>> fallback = selector.get_fallback("gpt-4-turbo")
            >>> print(fallback)
            'gpt-3.5-turbo'
        """
        try:
            idx = self.fallback_chain.index(failed_model)
            if idx + 1 < len(self.fallback_chain):
                return self.fallback_chain[idx + 1]
        except ValueError:
            # Model not in fallback chain, return first fallback
            if self.fallback_chain:
                return self.fallback_chain[0]

        return None

    def get_capabilities(self, model: str) -> ModelCapabilities | None:
        """Get capabilities for a model.

        Args:
            model: Model name

        Returns:
            Model capabilities or None if unknown

        Example:
            >>> caps = selector.get_capabilities("gpt-4-turbo")
            >>> print(caps.max_tokens)
            128000
        """
        return self.model_capabilities.get(model)

    def estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost for a model call.

        Args:
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD

        Example:
            >>> cost = selector.estimate_cost("gpt-4-turbo", 1000, 500)
            >>> print(f"${cost:.4f}")
            $0.0250
        """
        caps = self.get_capabilities(model)
        if not caps:
            return 0.0

        input_cost = (input_tokens / 1000) * caps.cost_per_1k_input
        output_cost = (output_tokens / 1000) * caps.cost_per_1k_output

        return input_cost + output_cost

    def _build_context(self, prompt: str, context: dict[str, Any]) -> dict[str, Any]:
        """Build context for strategy matching.

        Args:
            prompt: The prompt text
            context: User-provided context

        Returns:
            Complete context dictionary
        """
        ctx = context.copy()

        # Add token count if not provided
        if "tokens" not in ctx and "token_count" not in ctx:
            # Use simple estimation to avoid async call
            # Count tokens as roughly 4 characters per token
            estimated_tokens = len(prompt) // 4 + 1
            ctx["tokens"] = estimated_tokens
            ctx["token_count"] = estimated_tokens

        # Detect prompt characteristics
        ctx["has_code"] = ctx.get(
            "has_code",
            "```" in prompt or "def " in prompt or "function " in prompt,
        )
        ctx["has_url"] = ctx.get("has_url", "http://" in prompt or "https://" in prompt)
        ctx["is_question"] = ctx.get("is_question", "?" in prompt)
        ctx["prompt_length"] = len(prompt)

        return ctx

    def _filter_by_capabilities(
        self,
        required_capabilities: list[str] | None,
    ) -> list[str]:
        """Filter models by required capabilities.

        Args:
            required_capabilities: List of required capability names

        Returns:
            List of model names that meet requirements
        """
        if not required_capabilities:
            return list(self.model_capabilities.keys())

        available = []
        for model, caps in self.model_capabilities.items():
            if all(getattr(caps, cap, False) for cap in required_capabilities):
                available.append(model)

        return available


def create_cost_optimized_selector(
    budget_per_1k_tokens: float = 2.0,
) -> ModelSelector:
    """Create a cost-optimized model selector."""
    from quadkit.ai.llm.selection._scoring import (
        create_cost_optimized_selector as _create,
    )

    return _create(budget_per_1k_tokens=budget_per_1k_tokens)


def create_quality_optimized_selector() -> ModelSelector:
    """Create a quality-optimized model selector."""
    from quadkit.ai.llm.selection._scoring import (
        create_quality_optimized_selector as _create,
    )

    return _create()


def create_balanced_selector() -> ModelSelector:
    """Create a balanced model selector."""
    from quadkit.ai.llm.selection._scoring import create_balanced_selector as _create

    return _create()
