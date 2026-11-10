"""Integration tests using Ollama for real LLM functionality.

These tests require Ollama to be running with appropriate models.
Run with: pytest -m integration
"""

import pytest

try:
    import pytest_asyncio
except ImportError:
    pytest_asyncio = None

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.clients.ollama import OllamaClient
from quadkit.ai.llm.types import ChatMessage, Role


@pytest.mark.skip(
    reason="Skipping Ollama integration tests due to resource limitations with local LLM models",
)
class TestOllamaIntegration:
    """Integration tests using real Ollama models."""

    @ pytest.fixture if pytest_asyncio is None else pytest_asyncio.fixture
    async def ollama_client(self):
        """Ollama client fixture."""
        config = ClientConfig(
            provider="ollama",
            model="qwen2.5-coder:32b-instruct-q4_K_M",  # Use available model
            api_base="http://localhost:11434",
            temperature=0.1,  # Low temperature for consistent results
            max_tokens=100,
        )
        client = OllamaClient(config)
        yield client
        await client.close()

    @pytest.mark.asyncio
    async def test_basic_completion(self, ollama_client):
        """Test basic text completion with Ollama."""
        messages = [
            ChatMessage(
                role=Role.USER, content="What is 2 + 2? Answer with just the number.",
            ),
        ]

        completion = await ollama_client.complete(messages=messages)

        assert completion is not None
        assert completion.content is not None
        assert len(completion.content.strip()) > 0
        assert completion.model == "qwen2.5-coder:32b-instruct-q4_K_M"
        assert completion.finish_reason in ["stop", "length", None]

        # Should contain "4" in the response
        assert "4" in completion.content

    @pytest.mark.asyncio
    async def test_streaming_completion(self, ollama_client):
        """Test streaming completion with Ollama."""
        messages = [
            ChatMessage(
                role=Role.USER, content="Count from 1 to 5, one number per line.",
            ),
        ]

        chunks = []
        async for chunk in ollama_client.stream_chat(messages=messages):
            chunks.append(chunk)

        assert len(chunks) > 0

        # Combine all chunks
        full_content = "".join(chunk.delta or "" for chunk in chunks)

        assert len(full_content.strip()) > 0
        # Should contain numbers 1-5
        assert "1" in full_content
        assert "2" in full_content
        assert "3" in full_content
        assert "4" in full_content
        assert "5" in full_content

    @pytest.mark.asyncio
    async def test_conversation_memory(self, ollama_client):
        """Test conversation with memory."""
        # First message
        messages = [
            ChatMessage(
                role=Role.SYSTEM,
                content="You are a helpful assistant. Remember that my favorite color is blue.",
            ),
            ChatMessage(role=Role.USER, content="What is my favorite color?"),
        ]

        completion1 = await ollama_client.complete(messages=messages)
        assert "blue" in completion1.content.lower()

        # Follow-up question
        messages.append(ChatMessage(role=Role.ASSISTANT, content=completion1.content))
        messages.append(
            ChatMessage(
                role=Role.USER,
                content="What about my favorite food? I never mentioned it.",
            ),
        )

        completion2 = await ollama_client.complete(messages=messages)
        # Should indicate it doesn't know about favorite food or offer to remember it
        content_lower = completion2.content.lower()
        assert any(
            word in content_lower
            for word in [
                "don't know",
                "didn't mention",
                "not specified",
                "unknown",
                "haven't mentioned",
                "never mentioned",
                "tell me",
                "remember it",
            ]
        )

    @pytest.mark.asyncio
    async def test_code_generation(self, ollama_client):
        """Test code generation capabilities."""
        messages = [
            ChatMessage(
                role=Role.USER,
                content="Write a Python function that calculates the factorial of a number using recursion. Include a docstring.",
            ),
        ]

        completion = await ollama_client.complete(
            messages=messages,
            temperature=0.2,
            max_tokens=200,
        )

        content = completion.content.lower()
        assert "def" in content
        assert "factorial" in content
        assert "return" in content
        # Should contain recursive logic
        assert "factorial" in content and ("n-1" in content or "n - 1" in content)
