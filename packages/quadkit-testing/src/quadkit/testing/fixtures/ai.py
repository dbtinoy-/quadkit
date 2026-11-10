from __future__ import annotations

"""Pytest fixtures for AI/ML testing."""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest

from quadkit.testing.clients.ai import AITestBed, AITestClient, AITestData

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Prefer pytest-asyncio's async fixtures when available; fall back to pytest.fixture.
_async_fixture: Callable[..., Any] = pytest.fixture
try:
    import pytest_asyncio
except ImportError:
    pass
else:
    _async_fixture = pytest_asyncio.fixture


@pytest.fixture
def intelligence_test_bed() -> AITestBed:
    """Create an intelligence test bed."""
    return AITestBed()


@pytest.fixture
def intelligence_test_client(intelligence_test_bed: AITestBed) -> AITestClient:
    """Create an intelligence test client."""
    return intelligence_test_bed.create_test_client()


@pytest.fixture
def intelligence_test_data() -> AITestData:
    """Create intelligence test data."""
    return AITestData()


@_async_fixture
async def llm_client(intelligence_test_bed: AITestBed) -> AsyncGenerator[Any, None]:
    """Create an LLM client for testing."""
    client = await intelligence_test_bed.get_llm_client()
    yield client


@_async_fixture
async def vector_store(intelligence_test_bed: AITestBed) -> AsyncGenerator[Any, None]:
    """Create a vector store for testing."""
    store = await intelligence_test_bed.get_vector_store()
    yield store


@_async_fixture
async def ml_predictor(intelligence_test_bed: AITestBed) -> AsyncGenerator[Any, None]:
    """Create an ML predictor for testing."""
    predictor = await intelligence_test_bed.get_ml_predictor()
    yield predictor


@pytest.fixture
def sample_chat_messages(intelligence_test_bed: AITestBed) -> list[Any]:
    """Create sample chat messages for testing."""
    from quadkit.ai.llm.types import ChatMessage, Role

    return [
        ChatMessage(role=Role.SYSTEM, content="You are a helpful assistant."),
        ChatMessage(role=Role.USER, content="What is the capital of France?"),
    ]


@pytest.fixture
def sample_documents(intelligence_test_bed: AITestBed) -> list[Any]:
    """Create sample documents for testing."""
    from quadkit.contracts.ai.vector import Document

    return [
        Document(
            text="Paris is the capital of France.",
            id="doc1",
            metadata={"source": "geography"},
        ),
        Document(
            text="Berlin is the capital of Germany.",
            id="doc2",
            metadata={"source": "geography"},
        ),
        Document(
            text="Python is a programming language.",
            id="doc3",
            metadata={"source": "technology"},
        ),
    ]


@pytest.fixture
def sample_features(intelligence_test_bed: AITestBed) -> dict[str, Any]:
    """Create sample features for ML testing (backend-agnostic dict)."""
    return {
        "text": "This is a test input",
        "length": 18,
        "sentiment": 0.8,
        "category": "positive",
    }


@pytest.fixture
def sample_llm_responses() -> list[str]:
    """Create sample LLM responses."""
    return [
        "Paris is the capital of France.",
        "The answer is 42.",
        "Python is a great programming language.",
        "Machine learning is fascinating.",
    ]


@pytest.fixture
def sample_predictions() -> list[dict]:
    """Create sample ML predictions."""
    return [
        {"prediction": "positive", "confidence": 0.95},
        {"prediction": "negative", "confidence": 0.87},
        {"prediction": "neutral", "confidence": 0.92},
    ]


@_async_fixture
async def populated_vector_store(
    vector_store: Any,
    sample_documents: list[Any],
) -> AsyncGenerator[Any, None]:
    """Create a vector store populated with sample documents."""
    await vector_store.add(sample_documents)
    yield vector_store


@pytest.fixture
def mock_llm_client(intelligence_test_bed: AITestBed) -> MagicMock:
    """The test bed's mock LLM client (``complete`` is an AsyncMock)."""
    mock: MagicMock = intelligence_test_bed.mock_llm
    return mock


@pytest.fixture
def mock_vector_store(intelligence_test_bed: AITestBed) -> MagicMock:
    """The test bed's mock vector store (``add``/``search`` are AsyncMocks)."""
    mock: MagicMock = intelligence_test_bed.mock_vector_store
    return mock


@pytest.fixture
def mock_ml_predictor(intelligence_test_bed: AITestBed) -> MagicMock:
    """The test bed's mock ML predictor (``predict`` is an AsyncMock)."""
    mock: MagicMock = intelligence_test_bed.mock_ml_predictor
    return mock


@pytest.fixture
def intelligence_assertions(intelligence_test_client: AITestClient) -> dict:
    """Create assertion helpers for intelligence testing."""
    return {
        "assert_llm_completions_count": intelligence_test_client.assert_llm_completions_count,
        "assert_vector_searches_count": intelligence_test_client.assert_vector_searches_count,
        "assert_ml_predictions_count": intelligence_test_client.assert_ml_predictions_count,
    }


__all__ = [
    "intelligence_assertions",
    "intelligence_test_bed",
    "intelligence_test_client",
    "intelligence_test_data",
    "llm_client",
    "ml_predictor",
    "mock_llm_client",
    "mock_ml_predictor",
    "mock_vector_store",
    "populated_vector_store",
    "sample_chat_messages",
    "sample_documents",
    "sample_features",
    "sample_llm_responses",
    "sample_predictions",
    "vector_store",
]
