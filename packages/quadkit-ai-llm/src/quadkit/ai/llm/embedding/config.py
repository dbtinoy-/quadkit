"""Typed configuration dataclasses for embedding provider adapters."""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = [
    "CohereEmbeddingConfig",
    "EmbeddingConfig",
    "JinaEmbeddingConfig",
    "LocalEmbeddingConfig",
    "OpenAIEmbeddingConfig",
    "VoyageEmbeddingConfig",
]


@dataclass(frozen=True)
class EmbeddingConfig:
    """Base configuration for embedding clients.

    Attributes:
        model: Model identifier to use for embedding.
        dimensions: Output vector dimensions (None = provider default).
        batch_size: Number of texts per API batch.
        timeout: Request timeout in seconds.
    """

    model: str
    dimensions: int | None = None
    batch_size: int = 100
    timeout: float = 30.0


@dataclass(frozen=True)
class OpenAIEmbeddingConfig(EmbeddingConfig):
    """Configuration for the OpenAI embedding adapter.

    Attributes:
        model: Embedding model ID (default: text-embedding-3-small).
        api_key: OpenAI API key (falls back to OPENAI_API_KEY env var when None).
        base_url: Custom API base URL (useful for Azure / proxy deployments).
        organization: Optional OpenAI organization ID.
    """

    model: str = "text-embedding-3-small"
    api_key: str | None = field(default=None, repr=False)
    base_url: str = "https://api.openai.com/v1"
    organization: str | None = None


@dataclass(frozen=True)
class CohereEmbeddingConfig(EmbeddingConfig):
    """Configuration for the Cohere embedding adapter.

    Attributes:
        model: Cohere model ID (default: embed-english-v3.0).
        api_key: Cohere API key.
        input_type: Input type hint sent to Cohere (e.g. search_document).
    """

    model: str = "embed-english-v3.0"
    api_key: str | None = field(default=None, repr=False)
    input_type: str = "search_document"
    base_url: str = "https://api.cohere.com"


@dataclass(frozen=True)
class VoyageEmbeddingConfig(EmbeddingConfig):
    """Configuration for the Voyage AI embedding adapter.

    Attributes:
        model: Voyage model ID (default: voyage-3).
        api_key: Voyage API key.
        base_url: Custom API base URL.
    """

    model: str = "voyage-3"
    api_key: str | None = field(default=None, repr=False)
    base_url: str = "https://api.voyageai.com/v3"


@dataclass(frozen=True)
class JinaEmbeddingConfig(EmbeddingConfig):
    """Configuration for the Jina embedding adapter.

    Attributes:
        model: Jina model ID (default: jina-embeddings-v3).
        api_key: Jina API key.
        base_url: Custom API base URL.
    """

    model: str = "jina-embeddings-v3"
    api_key: str | None = field(default=None, repr=False)
    base_url: str = "https://api.jina.ai/v1"


@dataclass(frozen=True)
class LocalEmbeddingConfig(EmbeddingConfig):
    """Configuration for the local (sentence-transformers) embedding adapter.

    Attributes:
        model: HuggingFace model ID (default: all-MiniLM-L6-v2).
        device: Compute device (cpu or cuda).
        cache_dir: Directory to cache downloaded models.
    """

    model: str = "all-MiniLM-L6-v2"
    device: str = "cpu"
    cache_dir: str | None = None
