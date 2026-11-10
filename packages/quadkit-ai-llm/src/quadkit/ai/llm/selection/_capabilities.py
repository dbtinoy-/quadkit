"""Model capability definitions for LLM selection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelCapabilities:
    """Model capabilities and constraints."""

    max_tokens: int
    supports_functions: bool = False
    supports_vision: bool = False
    supports_streaming: bool = True
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    avg_latency_ms: float = 2000.0
    quality_score: float = 0.8


DEFAULT_MODEL_CAPABILITIES: dict[str, ModelCapabilities] = {
    "gpt-4-turbo": ModelCapabilities(
        max_tokens=128000,
        supports_functions=True,
        supports_vision=True,
        supports_streaming=True,
        cost_per_1k_input=10.0,
        cost_per_1k_output=30.0,
        avg_latency_ms=2000,
        quality_score=0.95,
    ),
    "gpt-4": ModelCapabilities(
        max_tokens=8192,
        supports_functions=True,
        supports_vision=False,
        supports_streaming=True,
        cost_per_1k_input=30.0,
        cost_per_1k_output=60.0,
        avg_latency_ms=2500,
        quality_score=0.95,
    ),
    "gpt-3.5-turbo": ModelCapabilities(
        max_tokens=16385,
        supports_functions=True,
        supports_vision=False,
        supports_streaming=True,
        cost_per_1k_input=0.5,
        cost_per_1k_output=1.5,
        avg_latency_ms=800,
        quality_score=0.75,
    ),
    "claude-3-opus-20240229": ModelCapabilities(
        max_tokens=200000,
        supports_functions=True,
        supports_vision=True,
        supports_streaming=True,
        cost_per_1k_input=15.0,
        cost_per_1k_output=75.0,
        avg_latency_ms=2500,
        quality_score=0.98,
    ),
    "claude-3-sonnet-20240229": ModelCapabilities(
        max_tokens=200000,
        supports_functions=True,
        supports_vision=True,
        supports_streaming=True,
        cost_per_1k_input=3.0,
        cost_per_1k_output=15.0,
        avg_latency_ms=1500,
        quality_score=0.90,
    ),
    "claude-3-haiku-20240307": ModelCapabilities(
        max_tokens=200000,
        supports_functions=True,
        supports_vision=True,
        supports_streaming=True,
        cost_per_1k_input=0.25,
        cost_per_1k_output=1.25,
        avg_latency_ms=600,
        quality_score=0.70,
    ),
    "ollama/llama3": ModelCapabilities(
        max_tokens=8192,
        supports_functions=False,
        supports_vision=False,
        supports_streaming=True,
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
        avg_latency_ms=5000,
        quality_score=0.75,
    ),
}
