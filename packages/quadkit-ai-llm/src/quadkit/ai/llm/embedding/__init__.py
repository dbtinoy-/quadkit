"""Embedding provider adapters and registry.

Provides a unified interface for multiple embedding providers including OpenAI,
Cohere, Voyage, Jina, and local models via sentence-transformers.
"""

from __future__ import annotations

from quadkit.ai.llm.embedding.base import (
    AbstractEmbeddingAdapter,
    EmbeddingModelInfo,
)
from quadkit.ai.llm.embedding.cohere import CohereEmbeddingAdapter
from quadkit.ai.llm.embedding.config import (
    CohereEmbeddingConfig,
    EmbeddingConfig,
    JinaEmbeddingConfig,
    LocalEmbeddingConfig,
    OpenAIEmbeddingConfig,
    VoyageEmbeddingConfig,
)
from quadkit.ai.llm.embedding.jina import JinaEmbeddingAdapter
from quadkit.ai.llm.embedding.local import LocalEmbeddingAdapter
from quadkit.ai.llm.embedding.openai import OpenAIEmbeddingAdapter
from quadkit.ai.llm.embedding.registry import EmbeddingProviderRegistry
from quadkit.ai.llm.embedding.voyage import VoyageEmbeddingAdapter

__all__ = [
    "AbstractEmbeddingAdapter",
    "CohereEmbeddingAdapter",
    "CohereEmbeddingConfig",
    "EmbeddingConfig",
    "EmbeddingModelInfo",
    "EmbeddingProviderRegistry",
    "JinaEmbeddingAdapter",
    "JinaEmbeddingConfig",
    "LocalEmbeddingAdapter",
    "LocalEmbeddingConfig",
    "OpenAIEmbeddingAdapter",
    "OpenAIEmbeddingConfig",
    "VoyageEmbeddingAdapter",
    "VoyageEmbeddingConfig",
]
