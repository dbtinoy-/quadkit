"""LLM constants — provider names, defaults, and metric identifiers."""

from __future__ import annotations

import importlib.metadata

try:
    __version__: str = importlib.metadata.version("quadkit-ai-llm")
except ImportError:
    __version__ = "0.0.0"


# -- Environment Variable Prefixes -------------------------------------------
ENV_PREFIX: str = "QK_AI_LLM__"
"""Environment variable prefix for LLM configuration."""

ENV_NESTED_DELIMITER: str = "__"
"""Delimiter for nested env var keys."""


# ---------------------------------------------------------------------------
# Provider names
# ---------------------------------------------------------------------------

PROVIDER_OPENAI: str = "openai"
PROVIDER_ANTHROPIC: str = "anthropic"
PROVIDER_OLLAMA: str = "ollama"
PROVIDER_COHERE: str = "cohere"
PROVIDER_GROQ: str = "groq"
PROVIDER_MISTRAL: str = "mistral"
PROVIDER_OPENROUTER: str = "openrouter"

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_TEMPERATURE: float = 0.7
DEFAULT_MAX_TOKENS: int = 2048
DEFAULT_TIMEOUT_S: int = 30
DEFAULT_MAX_RETRIES: int = 3

# ---------------------------------------------------------------------------
# MetricProtocol names
# ---------------------------------------------------------------------------

METRIC_LLM_REQUESTS_TOTAL: str = "ai.llm.requests.total"
METRIC_LLM_REQUEST_DURATION_MS: str = "ai.llm.request.duration_ms"
METRIC_LLM_TOKENS_INPUT: str = "ai.llm.tokens.input"
METRIC_LLM_TOKENS_OUTPUT: str = "ai.llm.tokens.output"
METRIC_LLM_CACHE_HITS: str = "ai.llm.cache.hits"

__all__ = [
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TIMEOUT_S",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "METRIC_LLM_CACHE_HITS",
    "METRIC_LLM_REQUESTS_TOTAL",
    "METRIC_LLM_REQUEST_DURATION_MS",
    "METRIC_LLM_TOKENS_INPUT",
    "METRIC_LLM_TOKENS_OUTPUT",
    "PROVIDER_ANTHROPIC",
    "PROVIDER_COHERE",
    "PROVIDER_GROQ",
    "PROVIDER_MISTRAL",
    "PROVIDER_OLLAMA",
    "PROVIDER_OPENAI",
    "PROVIDER_OPENROUTER",
    "__version__",
]
