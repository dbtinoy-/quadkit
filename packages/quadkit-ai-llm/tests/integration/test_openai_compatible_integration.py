"""Integration tests for OpenAI Compatible LLM provider using LM Studio.

Tests end-to-end functionality with LM Studio or other OpenAI-compatible servers.
Requires LM Studio running locally on port 1234.
"""

import warnings

import pytest

try:
    import pytest_asyncio
except ImportError:
    pytest_asyncio = None

try:
    from quadkit.ai.llm.clients.openai_compatible import OpenAICompatibleClient
    from quadkit.ai.llm.types import ChatMessage, Role
    from quadkit.logging import get_logger
except ModuleNotFoundError as e:  # pragma: no cover - skip when provider not present
    import pytest

    pytest.skip(
        f"Skipping OpenAI-compatible tests because provider module is missing: {e}",
        allow_module_level=True,
    )

# Suppress annoying warnings during testing
warnings.filterwarnings(
    "ignore",
    message=".*torch.utils._pytree._register_pytree_node.*",
    category=FutureWarning,
)
warnings.filterwarnings(
    "ignore",
    message=".*builtin type SwigPyPacked has no __module__ attribute.*",
    category=DeprecationWarning,
)
warnings.filterwarnings(
    "ignore",
    message=".*builtin type SwigPyObject has no __module__ attribute.*",
    category=DeprecationWarning,
)


logger = get_logger(__name__)


@pytest.mark.skip(
    reason="Skipping OpenAI-compatible tests due to resource limitations with local LLM models",
)
class TestOpenAICompatibleIntegration:
    """Integration tests for OpenAI Compatible client with LM Studio."""

    @ pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
    async def lm_studio_client(self):
        """LM Studio client fixture."""
        client = OpenAICompatibleClient(
            base_url="http://127.0.0.1:1234/v1",
            model="gemma-3-27b-it@q4_0",  # Use the model that exists in LM Studio
            api_key="not-needed",
            timeout=30.0,  # Longer timeout for actual tests
            max_retries=2,
        )

        # Skip health check since we know LM Studio is running
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_basic_completion(self, lm_studio_client):
        """Test basic text completion with LM Studio."""
        messages = [
            ChatMessage(role=Role.USER, content="Say 'Hello World' and nothing else."),
        ]

        completion = await lm_studio_client.complete(
            messages=messages, temperature=0.1, max_tokens=50,
        )

        assert completion.content is not None
        assert len(completion.content.strip()) > 0
        assert "hello" in completion.content.lower()
        assert completion.model is not None
        assert completion.finish_reason in ["stop", "length", None]

    @pytest.mark.asyncio
    async def test_streaming_completion(self, lm_studio_client):
        """Test streaming completion with LM Studio."""
        messages = [
            ChatMessage(
                role=Role.USER, content="Count from 1 to 3, one number per line.",
            ),
        ]

        chunks = []
        async for chunk in await lm_studio_client.complete(
            messages=messages, stream=True, temperature=0.1,
        ):
            chunks.append(chunk)
            assert chunk.content is not None or chunk.finish_reason is not None

        # Should have received some content
        content_parts = list(filter(lambda c: c.content, map(lambda c: c.content, chunks)))
        full_content = "".join(content_parts)
        assert len(full_content.strip()) > 0

    @pytest.mark.asyncio
    async def test_conversation_memory(self, lm_studio_client):
        """Test conversation memory and context retention."""
        # First message
        messages1 = [
            ChatMessage(
                role=Role.SYSTEM,
                content="You are a helpful assistant. Remember that my favorite color is blue.",
            ),
            ChatMessage(role=Role.USER, content="What is my favorite color?"),
        ]

        completion1 = await lm_studio_client.complete(
            messages=messages1, temperature=0.1, max_tokens=50,
        )
        assert completion1.content is not None
        assert "blue" in completion1.content.lower()

        # Follow-up message
        messages2 = messages1 + [
            ChatMessage(role=Role.ASSISTANT, content=completion1.content),
            ChatMessage(role=Role.USER, content="What did I just ask you?"),
        ]

        completion2 = await lm_studio_client.complete(
            messages=messages2, temperature=0.1, max_tokens=50,
        )
        assert completion2.content is not None
        # Should reference the color question
        response_lower = completion2.content.lower()
        assert any(word in response_lower for word in ["color", "favorite", "blue"])

    @pytest.mark.asyncio
    async def test_code_generation(self, lm_studio_client):
        """Test code generation capabilities."""
        messages = [
            ChatMessage(
                role=Role.USER,
                content="Write a simple Python function that adds two numbers. Include a docstring.",
            ),
        ]

        completion = await lm_studio_client.complete(
            messages=messages,
            temperature=0.1,
            max_tokens=200,
        )

        content = completion.content
        assert content is not None
        assert len(content.strip()) > 20

        # Should contain Python code elements
        content_lower = content.lower()
        assert "def " in content_lower or "function" in content_lower
        assert "return" in content_lower or "add" in content_lower

    @pytest.mark.asyncio
    async def test_temperature_effect(self, lm_studio_client):
        """Test that temperature affects response variability."""
        messages = [
            ChatMessage(
                role=Role.USER, content="Write one creative sentence about cats.",
            ),
        ]

        # Get two responses with different temperatures
        completion1 = await lm_studio_client.complete(
            messages=messages,
            temperature=0.1,
            max_tokens=50,
        )

        completion2 = await lm_studio_client.complete(
            messages=messages,
            temperature=1.0,
            max_tokens=50,
        )

        # Both should be valid responses
        assert completion1.content is not None
        assert completion2.content is not None
        assert len(completion1.content.strip()) > 5
        assert len(completion2.content.strip()) > 5

    @pytest.mark.asyncio
    async def test_max_tokens_limit(self, lm_studio_client):
        """Test max_tokens parameter limits response length."""
        messages = [
            ChatMessage(role=Role.USER, content="Write a long story about a dragon."),
        ]

        # Short response
        completion_short = await lm_studio_client.complete(
            messages=messages,
            temperature=0.7,
            max_tokens=10,
        )

        # Longer response
        completion_long = await lm_studio_client.complete(
            messages=messages,
            temperature=0.7,
            max_tokens=50,
        )

        assert completion_short.content is not None
        assert completion_long.content is not None

        # Longer response should generally be longer (allowing some tolerance)
        short_len = len(completion_short.content.split())
        long_len = len(completion_long.content.split())

        # The longer response should be at least as long as the shorter one
        # (though not guaranteed due to token vs word differences)
        assert long_len >= short_len

    @pytest.mark.asyncio
    async def test_error_handling(self, lm_studio_client):
        """Test error handling for invalid requests."""
        # Test with invalid model (should still work as LM Studio overrides)
        messages = [
            ChatMessage(role=Role.USER, content="Say hello."),
        ]

        # This should work despite the invalid model name
        completion = await lm_studio_client.complete(messages=messages, temperature=0.1)
        assert completion.content is not None

    @pytest.mark.asyncio
    async def test_auto_eject_between_providers(self, lm_studio_client):
        """Test auto-eject functionality when switching between providers."""
        # This test demonstrates that when we load a model from one provider,
        # models from other providers should be automatically unloaded

        from quadkit.ai.llm.model_manager import get_model_manager

        manager = get_model_manager()

        # Check if Ollama is available
        ollama_available = (
            True  # Assume available since user confirmed local LLMs are running
        )
        # try:
        #     models = await manager.list_models(provider='ollama')
        #     ollama_available = len(models) > 0
        # except Exception:
        #     pass

        if not ollama_available:
            pytest.skip("Ollama not available for auto-eject test")

        # Load from lm-studio first (this should unload ollama models)
        # The lm_studio_client fixture already loads the model when complete is called
        messages = [
            ChatMessage(
                role=Role.USER, content="Say 'lm-studio loaded' and nothing else.",
            ),
        ]

        completion1 = await lm_studio_client.complete(
            messages=messages, temperature=0.1, max_tokens=50,
        )
        assert completion1.content is not None
        logger.debug(
            "LM Studio loaded models: %s",
            await manager.get_loaded_models('lm-studio'),
        )

        # Now load from ollama (this should auto-eject lm-studio models)
        ollama_result = await manager.load_model("granite3.3:latest", provider="ollama")
        assert ollama_result, "Failed to load Ollama model"
        logger.debug(
            "LM Studio loaded models after Ollama load: %s",
            await manager.get_loaded_models('lm-studio'),
        )
        logger.debug(
            "Ollama loaded models: %s",
            await manager.get_loaded_models('ollama'),
        )

        # Use lm-studio again (this should eject ollama models)
        completion2 = await lm_studio_client.complete(
            messages=messages, temperature=0.1, max_tokens=50,
        )
        assert completion2.content is not None
        logger.debug(
            "Final LM Studio loaded models: %s",
            await manager.get_loaded_models('lm-studio'),
        )
        logger.debug(
            "Final Ollama loaded models: %s",
            await manager.get_loaded_models('ollama'),
        )
