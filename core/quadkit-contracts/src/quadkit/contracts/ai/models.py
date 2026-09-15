"""AI model request and response types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.contracts.ai.types import ModelCapability


@dataclass(frozen=True)
class ModelRequest:
    """Request to execute an LLM model.

    Attributes:
        prompt: The input prompt or messages
        model_id: Optional specific model to use (overrides capability-based selection)
        temperature: Sampling temperature (0.0 to 2.0, lower = deterministic)
        max_tokens: Maximum tokens in the response
        top_p: Nucleus sampling parameter
        top_k: Top-k sampling parameter
        required_capabilities: Set of capabilities the model must support
        extra_params: Additional provider-specific parameters
    """

    prompt: str
    model_id: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    top_k: int | None = None
    required_capabilities: set[ModelCapability] | None = None
    extra_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelResponse:
    """Response from an LLM model.

    Attributes:
        content: The generated content (text)
        tokens_used: Total tokens consumed (input + output)
        stop_reason: Why generation stopped (completion, length, stop_sequence, etc.)
        extra_metadata: Additional response metadata
    """

    content: str
    tokens_used: int = 0
    stop_reason: str | None = None
    extra_metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ["ModelRequest", "ModelResponse"]
