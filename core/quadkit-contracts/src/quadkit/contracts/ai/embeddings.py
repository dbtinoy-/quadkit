"""Embedding contracts for Quadkit.

Defines embeddings classes analogous to LangChain's embeddings.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Embeddings(ABC):
    """Embeddings base class (like LangChain's Embeddings).

    Provides interface for embedding documents and queries.
    """

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents.

        Args:
            texts: List of text documents.

        Returns:
            List of embedding vectors.
        """
        ...

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed a single query.

        Args:
            text: Query text.

        Returns:
            Embedding vector.
        """
        ...


class FakeEmbeddings(Embeddings):
    """Fake embeddings for testing (like LangChain's FakeEmbeddings)."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed documents with fake embeddings."""
        dimension = 384
        return [[0.1] * dimension for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        """Embed query with fake embeddings."""
        dimension = 384
        return [0.1] * dimension


__all__ = [
    "Embeddings",
    "FakeEmbeddings",
]
