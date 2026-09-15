"""Tests for Embedding contracts."""
from __future__ import annotations


def test_embeddings_embed_documents():
    """Embeddings should embed documents."""
    from quadkit.contracts.ai.embeddings import Embeddings
    
    class FakeEmbeddings(Embeddings):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[0.1, 0.2] for _ in texts]
        
        def embed_query(self, text: str) -> list[float]:
            return [0.1, 0.2]
    
    emb = FakeEmbeddings()
    result = emb.embed_documents(["hello", "world"])
    assert len(result) == 2
    assert len(result[0]) == 2


def test_embeddings_embed_query():
    """Embeddings should embed a single query."""
    from quadkit.contracts.ai.embeddings import Embeddings
    
    class FakeEmbeddings(Embeddings):
        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[0.1, 0.2] for _ in texts]
        
        def embed_query(self, text: str) -> list[float]:
            return [0.3, 0.4]
    
    emb = FakeEmbeddings()
    result = emb.embed_query("hello")
    assert result == [0.3, 0.4]
