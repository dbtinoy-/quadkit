"""Tests for AI testing client."""

import importlib.util
import os
import sys

import pytest

# Add src to path to import directly

# Mock dependencies before loading modules
class MockTestEnvironment:
    """Mock test environment for testing."""
    def __init__(self, name="mock"):
        self.name = name
        self.app = None
        self.container = None
        self._overrides = {}
        self._providers = []
    
    def use_provider(self, provider):
        self._providers.append(provider)
    
    def override(self, service, impl):
        self._overrides[service] = impl
    
    async def setup(self):
        self.app = "mock_app"
        self.container = "mock_container"
        # Start all providers
        for provider in self._providers:
            if hasattr(provider, "start"):
                await provider.start()
        return self.app
    
    async def teardown(self):
        # Stop all providers
        for provider in self._providers:
            if hasattr(provider, "stop"):
                await provider.stop()
        self.app = None
        self.container = None
    
    async def __aenter__(self):
        await self.setup()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.teardown()

class MockChatMessage:
    """Mock chat message."""
    def __init__(self, content="test"):
        self.content = content

class MockCompletion:
    """Mock completion."""
    def __init__(self, text="test"):
        self.text = text

class MockFeatures:
    """Mock features."""
    def __init__(self, data=None):
        self.data = data or {}

class MockPrediction:
    """Mock prediction."""
    def __init__(self, value="test"):
        self.value = value

class MockSearchResult:
    """Mock search result."""
    def __init__(self, score=1.0):
        self.score = score

class MockLLMClient:
    """Mock LLM client."""
    def __init__(self):
        self.responses = []

class MockVectorStore:
    """Mock vector store."""
    def __init__(self):
        self.vectors = []

# Mock the modules
# sys.modules["quadkit.testing.bed"] = type("MockModule", (), {"TestEnvironment": MockTestEnvironment})
# sys.modules["quadkit.ai.llm.types"] = type("MockModule", (), {
#     "ChatMessage": MockChatMessage,
#     "Completion": MockCompletion,
# })
# sys.modules["quadkit.ai.ml.types"] = type("MockModule", (), {
#     "Features": MockFeatures,
#     "Prediction": MockPrediction,
# })
# sys.modules["quadkit.ai.vector.types"] = type("MockModule", (), {"SearchResult": Mock RAGSearchResult})
# sys.modules["quadkit.contracts"] = type("MockModule", (), {
#     "LLMClientProtocol": MockLLMClient,
#     "VectorStoreProtocol": MockVectorStore,
# })

# Import ai_client normally
from quadkit.testing.clients.ai import AITestData, AITestClient, AITestBed


class TestAITestData:
    """Test AITestData functionality."""

    def test_ai_test_data_creation(self):
        """Test basic AITestData creation."""
        data = AITestData("test")

        assert data.prefix == "test"
        assert data._llm_completions == []
        assert data._vector_searches == []
        assert data._ml_predictions == []
        assert data._pipeline_operations == []
        assert data._rag_operations == []
        assert data._agent_operations == []
        assert data._time_advances == []
        assert data._mock_responses == {}

    def test_ai_test_data_with_custom_prefix(self):
        """Test AITestData with custom prefix."""
        data = AITestData("custom")

        assert data.prefix == "custom"

    def test_adding_ai_operations(self):
        """Test adding different types of AI operations."""
        data = AITestData()

        # Mock operation data
        completion = {"response": "Hello", "tokens": 10}
        search = {"query": "test", "results": ["doc1", "doc2"]}
        prediction = {"input": [1, 2, 3], "output": 0.95}
        pipeline_op = {"stage": "preprocessing", "duration": 0.5}
        rag_op = {"query": "test query", "context": "relevant docs"}
        agent_op = {"action": "search", "result": "found"}

        data.add_llm_completion(completion)
        data.add_vector_search(search)
        data.add_ml_prediction(prediction)
        data.add_pipeline_operation(pipeline_op)
        data.add_rag_operation(rag_op)
        data.add_agent_operation(agent_op)
        data.record_time_advance(1.5)

        assert len(data._llm_completions) == 1
        assert len(data._vector_searches) == 1
        assert len(data._ml_predictions) == 1
        assert len(data._pipeline_operations) == 1
        assert len(data._rag_operations) == 1
        assert len(data._agent_operations) == 1
        assert data._time_advances == [1.5]

    def test_mock_responses(self):
        """Test mock response management."""
        data = AITestData()

        data.set_mock_response("llm", {"response": "mocked"})
        data.set_mock_response("vector", {"results": []})

        assert data.get_mock_response("llm") == {"response": "mocked"}
        assert data.get_mock_response("vector") == {"results": []}
        assert data.get_mock_response("nonexistent") is None


@pytest.mark.asyncio
class TestAITestClient:
    """Test AITestClient functionality."""

    async def test_ai_test_client_creation(self):
        """Test basic AITestClient creation."""
        # Mock test bed
        class MockTestBed:
            def __init__(self):
                self.test_data = AITestData()

        bed = MockTestBed()
        client = AITestClient(bed)

        assert client.test_bed is bed
        assert hasattr(client, "test_data")

    async def test_ai_test_client_methods_exist(self):
        """Test that AITestClient has expected methods."""
        # Mock test bed
        class MockTestBed:
            def __init__(self):
                self.test_data = AITestData()

        bed = MockTestBed()
        client = AITestClient(bed)

        # Check that key methods exist
        methods = [
            "complete_with_llm",
            "search_vector_store",
            "predict_with_ml",
            "assert_llm_completions_count",
            "assert_vector_searches_count",
            "assert_ml_predictions_count",
        ]

        for method in methods:
            assert hasattr(client, method)
            assert callable(getattr(client, method))


@pytest.mark.asyncio
class TestAITestBed:
    """Test AITestBed functionality."""

    async def test_ai_test_bed_creation(self):
        """Test basic AITestBed creation."""
        bed = AITestBed(name="ai-test")

        assert bed.name == "ai-test"
        assert isinstance(bed, AITestBed)

    async def test_ai_test_bed_setup(self):
        """Test AITestBed setup."""
        bed = AITestBed(name="ai-test")

        app = await bed.setup()

        assert bed.app is app
        assert bed.container is not None

        # Should have AI-related providers
        # (Exact providers depend on what's available)

    @pytest.mark.asyncio
    async def test_ai_test_bed_with_providers(self):
        """Test AITestBed with additional providers."""
        from quadkit.di.provider import Provider
        from quadkit.contracts.core import ProviderPriority

        class MockWebProvider(Provider):
            priority: ProviderPriority = ProviderPriority.DOMAIN

            def __init__(self) -> None:
                super().__init__(name="mock-web")
                self._started = False
                self._stopped = False

            @property
            def started(self) -> bool:
                return self._started

            @property
            def stopped(self) -> bool:
                return self._stopped

            async def register(self, container) -> None:  # type: ignore[override]
                pass

            async def boot(self, container=None) -> None:  # type: ignore[override]
                self._started = True

            async def shutdown(self) -> None:  # type: ignore[override]
                self._stopped = True

        bed = AITestBed(name="ai-test")
        web_provider = MockWebProvider()

        bed.use_provider(web_provider)

        await bed.setup()

        assert web_provider.started

        await bed.teardown()

        assert web_provider.stopped

    async def test_ai_test_bed_context_manager(self):
        """Test AITestBed as context manager."""
        bed = AITestBed(name="ai-test")

        async def test_context():
            async with bed:
                assert bed.app is not None
                assert bed.container is not None

            assert bed.app is None
            assert bed.container is None

        await test_context()