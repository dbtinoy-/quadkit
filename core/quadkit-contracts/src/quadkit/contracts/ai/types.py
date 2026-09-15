"""Shared AI/ML enum types for Quadkit.

These enumerations are used across multiple AI sub-packages and are placed
in quadkit-contracts so all packages can depend on them without circular imports.
"""

from __future__ import annotations

from enum import StrEnum


class ModelCapability(StrEnum):
    """Capabilities that an LLM model may expose."""

    CHAT = "chat"
    COMPLETION = "completion"
    EMBEDDING = "embedding"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"
    STREAMING = "streaming"
    JSON_MODE = "json_mode"
    AUDIO = "audio"
    CODE = "code"


class ModelProvider(StrEnum):
    """Supported AI/ML model providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    COHERE = "cohere"
    GROQ = "groq"
    MISTRAL = "mistral"
    OPENROUTER = "openrouter"
    AZURE_OPENAI = "azure-openai"
    AWS_BEDROCK = "aws-bedrock"
    GOOGLE_VERTEX = "google-vertex"
    GEMINI = "gemini"
    CLOUDFLARE = "cloudflare"
    DEEPSEEK = "deepseek"
    TOGETHER = "together"
    FIREWORKS = "fireworks"
    LMSTUDIO = "lmstudio"
    OPENAI_COMPATIBLE = "openai_compatible"
    CUSTOM = "custom"


class VectorProvider(StrEnum):
    """Supported vector database providers."""

    CHROMA = "chroma"
    QDRANT = "qdrant"
    PGVECTOR = "pgvector"
    WEAVIATE = "weaviate"
    PINECONE = "pinecone"
    MILVUS = "milvus"


class EmbeddingModel(StrEnum):
    """Supported embedding models."""

    OPENAI_SMALL = "text-embedding-3-small"
    OPENAI_LARGE = "text-embedding-3-large"
    OPENAI_ADA = "text-embedding-ada-002"
    SENTENCE_TRANSFORMERS = "sentence-transformers"


__all__ = [
    "EmbeddingModel",
    "ModelCapability",
    "ModelProvider",
    "VectorProvider",
]
