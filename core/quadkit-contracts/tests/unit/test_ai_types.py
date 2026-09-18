"""Tests for contracts AI types."""

import pytest

from quadkit.contracts.ai.types import (
    EmbeddingModel,
    ModelProvider,
    VectorProvider,
)


class TestModelProvider:
    """Tests for ModelProvider enum."""

    def test_model_provider_values(self) -> None:
        """Test ModelProvider enum values."""
        assert ModelProvider.OPENAI.value == "openai"
        assert ModelProvider.ANTHROPIC.value == "anthropic"
        assert ModelProvider.OLLAMA.value == "ollama"
        assert ModelProvider.COHERE.value == "cohere"
        assert ModelProvider.GROQ.value == "groq"
        assert ModelProvider.MISTRAL.value == "mistral"

    def test_model_provider_members(self) -> None:
        """Test ModelProvider has expected members."""
        members = list(ModelProvider)
        assert len(members) >= 10


class TestVectorProvider:
    """Tests for VectorProvider enum."""

    def test_vector_provider_values(self) -> None:
        """Test VectorProvider enum values."""
        assert VectorProvider.CHROMA.value == "chroma"
        assert VectorProvider.QDRANT.value == "qdrant"
        assert VectorProvider.PGVECTOR.value == "pgvector"
        assert VectorProvider.WEAVIATE.value == "weaviate"
        assert VectorProvider.PINECONE.value == "pinecone"
        assert VectorProvider.MILVUS.value == "milvus"

    def test_vector_provider_members(self) -> None:
        """Test VectorProvider has expected members."""
        members = list(VectorProvider)
        assert len(members) >= 5


class TestEmbeddingModel:
    """Tests for EmbeddingModel enum."""

    def test_embedding_model_values(self) -> None:
        """Test EmbeddingModel enum values."""
        assert EmbeddingModel.OPENAI_SMALL.value == "text-embedding-3-small"
        assert EmbeddingModel.OPENAI_LARGE.value == "text-embedding-3-large"
        assert EmbeddingModel.OPENAI_ADA.value == "text-embedding-ada-002"
        assert EmbeddingModel.SENTENCE_TRANSFORMERS.value == "sentence-transformers"

    def test_embedding_model_members(self) -> None:
        """Test EmbeddingModel has expected members."""
        members = list(EmbeddingModel)
        assert len(members) >= 4
