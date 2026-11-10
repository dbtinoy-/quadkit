"""Test model management integration with LLM clients."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.clients.ollama import OllamaClient
from quadkit.logging import get_logger

logger = get_logger(__name__)

try:
    from quadkit.ai.llm.clients.openai_compatible import OpenAICompatibleClient
    from quadkit.ai.llm.types import ChatMessage, Role
except ModuleNotFoundError as e:  # pragma: no cover - skip when provider not present
    import pytest

    pytest.skip(
        f"Skipping OpenAI-compatible model management tests because provider module is missing: {e}",
        allow_module_level=True,
    )


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skip(reason="Model-manager integration not yet wired into OllamaClient; tracked as future work")
async def test_ollama_client_model_management():
    """Test that OllamaClient uses model manager for automatic model loading."""
    config = ClientConfig(
        provider="ollama",
        model="llama3:8b",
        api_base="http://localhost:11434",
    )

    # Mock the model manager
    with patch(
        "quadkit.ai.llm.clients.ollama.get_model_manager",
    ) as mock_get_manager:
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager

        # Make switch_provider and load_model async
        mock_manager.switch_provider = AsyncMock()
        mock_manager.load_model = AsyncMock()

        # Mock Ollama client
        with patch("ollama.AsyncClient") as mock_ollama_client:
            mock_client = MagicMock()
            mock_ollama_client.return_value = mock_client

            # Mock response that returns the requested model
            async def mock_chat(**params):
                model = params.get("model", "llama3:8b")
                return {
                    "model": model,
                    "message": {"content": "Hello!", "role": "assistant"},
                    "prompt_eval_count": 10,
                    "eval_count": 5,
                    "total_duration": 1000000,
                    "load_duration": 500000,
                }

            mock_client.chat.side_effect = mock_chat

            client = OllamaClient(config)

            # Test completion with same model (should not switch)
            messages = [ChatMessage(role=Role.USER, content="Hello")]
            result = await client.complete(messages)

            # Should NOT switch provider for same model
            mock_manager.switch_provider.assert_not_called()
            mock_manager.load_model.assert_not_called()

            assert result.content == "Hello!"
            assert result.model == "llama3:8b"

            # Reset mocks
            mock_manager.reset_mock()

            # Test completion with different model (should switch and load)
            result2 = await client.complete(messages, model="mistral:7b")

            # Should switch provider and load new model
            mock_manager.switch_provider.assert_called_with("ollama")
            mock_manager.load_model.assert_called_with("mistral:7b")

            assert result2.content == "Hello!"
            assert result2.model == "mistral:7b"


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skip(reason="Model-manager integration not yet wired into OpenAICompatibleClient; tracked as future work")
async def test_openai_compatible_client_model_management():
    """Test that OpenAICompatibleClient uses model manager for LM Studio."""
    # Mock the model manager before creating the client
    with patch(
        "quadkit.ai.llm.clients.openai_compatible.get_model_manager",
    ) as mock_get_manager:
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager
        # Initially no current provider
        mock_manager.get_current_provider.return_value = None

        # Make switch_provider and load_model async
        mock_manager.switch_provider = AsyncMock()
        mock_manager.load_model = AsyncMock()

        client = OpenAICompatibleClient(
            base_url="http://localhost:1234/v1",
            model="gemma-3-27b-it@q4_0",
            api_key="dummy",
        )

        # Mock HTTP client and response
        with patch.object(client, "_get_client") as mock_get_client:
            mock_http_client = MagicMock()
            mock_get_client.return_value = mock_http_client

            # Mock response
            mock_response = MagicMock()

            async def json_side_effect():
                return {
                    "choices": [
                        {
                            "message": {"content": "Hello!", "role": "assistant"},
                            "finish_reason": "stop",
                        },
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15,
                    },
                    "model": "gemma-3-27b-it@q4_0",
                }

            mock_response.json = AsyncMock(side_effect=json_side_effect)
            mock_http_client.post = AsyncMock(return_value=mock_response)
            # Test completion with initial model (should switch provider and load)
            messages = [{"role": "user", "content": "Hello"}]
            result = await client.complete(messages)

            # Should switch provider and load model for first use
            mock_manager.switch_provider.assert_called_with("lm-studio")
            mock_manager.load_model.assert_called_with("gemma-3-27b-it@q4_0")

            assert result.content == "Hello!"
            assert result.model == "gemma-3-27b-it@q4_0"

            # Reset mocks
            mock_manager.reset_mock()

            # Update mock response for different model
            async def json_side_effect2():
                return {
                    "choices": [
                        {
                            "message": {"content": "Hello!", "role": "assistant"},
                            "finish_reason": "stop",
                        },
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15,
                    },
                    "model": "mistral-7b",
                }

            mock_response.json = MagicMock(side_effect=json_side_effect2)

            # Test completion with different model
            result2 = await client.complete(messages, model="mistral-7b")

            # Should switch provider again to ensure it's on lm-studio, and load new model
            mock_manager.switch_provider.assert_called_with("lm-studio")
            mock_manager.load_model.assert_called_with("mistral-7b")

            assert result2.content == "Hello!"
            assert result2.model == "mistral-7b"


if __name__ == "__main__":
    asyncio.run(test_ollama_client_model_management())
    asyncio.run(test_openai_compatible_client_model_management())
    logger.info("All model management integration tests passed!")
