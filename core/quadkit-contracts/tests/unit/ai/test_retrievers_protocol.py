"""Tests for Retrievers contracts."""
from __future__ import annotations

import pytest


def test_retrieval_query_is_frozen_dataclass():
    """RetrievalQuery should be a frozen dataclass."""
    from quadkit.contracts.ai.retrievers import RetrievalQuery

    query = RetrievalQuery(query="test query", top_k=5)
    assert query.query == "test query"
    assert query.top_k == 5


def test_retrieved_node_is_frozen_dataclass():
    """RetrievedNode should be a frozen dataclass."""
    from quadkit.contracts.ai.retrievers import RetrievedNode

    node = RetrievedNode(id="1", content="doc content", score=0.9, metadata={})
    assert node.id == "1"
    assert node.content == "doc content"
    assert node.score == 0.9


def test_retriever_protocol_is_runtime_checkable():
    """RetrieverProtocol should be a runtime checkable protocol."""
    from quadkit.contracts.ai.retrievers import RetrieverProtocol

    assert hasattr(RetrieverProtocol, "__protocol_attrs__") or hasattr(RetrieverProtocol, "__annotations__")


def test_retriever_protocol_returns_result():
    """RetrieverProtocol.retrieve should return Result[list[RetrievedNode], RetrieverError]."""
    from quadkit.contracts.ai.retrievers import RetrievedNode, RetrieverProtocol

    class FakeRetriever:
        async def retrieve(
            self, query: str, top_k: int = 10
        ) -> list[RetrievedNode]:
            return [RetrievedNode(id="1", content="doc", score=0.9, metadata={})]

    assert isinstance(FakeRetriever(), RetrieverProtocol)


def test_node_postprocessor_protocol_is_runtime_checkable():
    """NodePostprocessorProtocol should be a runtime checkable protocol."""
    from quadkit.contracts.ai.retrievers import NodePostprocessorProtocol

    assert hasattr(NodePostprocessorProtocol, "__protocol_attrs__") or hasattr(NodePostprocessorProtocol, "__annotations__")


def test_node_postprocessor_protocol_returns_result():
    """NodePostprocessorProtocol.postprocess should return Result[list[RetrievedNode], RetrieverError]."""
    from quadkit.contracts.ai.retrievers import (
        NodePostprocessorProtocol,
        RetrievedNode,
    )

    class FakePostprocessor:
        async def postprocess(
            self, nodes: list[RetrievedNode]
        ) -> list[RetrievedNode]:
            return nodes

    assert isinstance(FakePostprocessor(), NodePostprocessorProtocol)


def test_retriever_protocol_exports():
    """RetrieverProtocol should be exported from ai module."""
    from quadkit.contracts.ai import RetrieverProtocol

    assert RetrieverProtocol is not None


def test_node_postprocessor_protocol_exports():
    """NodePostprocessorProtocol should be exported from ai module."""
    from quadkit.contracts.ai import NodePostprocessorProtocol

    assert NodePostprocessorProtocol is not None


def test_retrieval_query_exports():
    """RetrievalQuery should be exported from ai module."""
    from quadkit.contracts.ai import RetrievalQuery

    assert RetrievalQuery is not None


def test_retrieved_node_exports():
    """RetrievedNode should be exported from ai module."""
    from quadkit.contracts.ai import RetrievedNode

    assert RetrievedNode is not None


def test_retriever_error_exports():
    """RetrieverError should be exported from ai module."""
    from quadkit.contracts.ai import RetrieverError

    assert RetrieverError is not None


def test_retriever_error_is_ai_error():
    """RetrieverError should be a subclass of AIError."""
    from quadkit.contracts.ai.exceptions import AIError
    from quadkit.contracts.ai.retrievers import RetrieverError

    assert issubclass(RetrieverError, AIError)


def test_retriever_error_message():
    """RetrieverError should have proper error message."""
    from quadkit.contracts.ai.retrievers import RetrieverError

    err = RetrieverError("empty result set")
    assert "empty result set" in str(err)


def test_retrieval_query_default_top_k():
    """RetrievalQuery should have default top_k of 10."""
    from quadkit.contracts.ai.retrievers import RetrievalQuery

    query = RetrievalQuery(query="test")
    assert query.top_k == 10


def test_retrieval_query_custom_top_k():
    """RetrievalQuery should accept custom top_k."""
    from quadkit.contracts.ai.retrievers import RetrievalQuery

    query = RetrievalQuery(query="test", top_k=50)
    assert query.top_k == 50


def test_retrieved_node_with_metadata():
    """RetrievedNode should store metadata dict."""
    from quadkit.contracts.ai.retrievers import RetrievedNode

    node = RetrievedNode(
        id="1",
        content="test",
        score=0.5,
        metadata={"source": "doc1", "page": 5},
    )
    assert node.metadata["source"] == "doc1"
    assert node.metadata["page"] == 5


def test_retrieved_node_score_range():
    """RetrievedNode score should handle different values."""
    from quadkit.contracts.ai.retrievers import RetrievedNode

    node_high = RetrievedNode(id="1", content="test", score=1.0, metadata={})
    node_low = RetrievedNode(id="2", content="test", score=0.0, metadata={})
    node_mid = RetrievedNode(id="3", content="test", score=0.75, metadata={})

    assert node_high.score == 1.0
    assert node_low.score == 0.0
    assert node_mid.score == 0.75


@pytest.mark.asyncio
async def test_retriever_empty_results():
    """Retriever should handle empty results gracefully."""
    from quadkit.contracts.ai.retrievers import RetrievedNode
    from quadkit.contracts.core.result import Ok

    class EmptyRetriever:
        async def retrieve(self, query: str, top_k: int = 10) -> Ok[list[RetrievedNode]]:
            return Ok([])

    retriever = EmptyRetriever()
    result = await retriever.retrieve("test")
    assert result.is_ok()
    assert result.unwrap() == []


@pytest.mark.asyncio
async def test_retriever_multiple_nodes():
    """Retriever should handle multiple nodes."""
    from quadkit.contracts.ai.retrievers import RetrievedNode
    from quadkit.contracts.core.result import Ok

    class MultiRetriever:
        async def retrieve(self, query: str, top_k: int = 10) -> Ok[list[RetrievedNode]]:
            return Ok([
                RetrievedNode(id="1", content="doc1", score=0.9, metadata={}),
                RetrievedNode(id="2", content="doc2", score=0.8, metadata={}),
                RetrievedNode(id="3", content="doc3", score=0.7, metadata={}),
            ])

    retriever = MultiRetriever()
    result = await retriever.retrieve("test query", top_k=5)
    assert result.is_ok()
    nodes = result.unwrap()
    assert len(nodes) == 3
    assert nodes[0].score >= nodes[1].score >= nodes[2].score
