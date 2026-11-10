"""Test that Anthropic client handles MessageContent with image parts."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

from quadkit.ai.llm.clients.anthropic import AnthropicClient
from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.types import ChatMessage
from quadkit.contracts.ai.llm import Role
from quadkit.contracts.ai.multimodal import ImageBase64Part, ImageUrlPart, TextPart


class TestAnthropicSerializeMessages:
    """Test Anthropic client multimodal message serialization."""

    def _make_client(self):
        """Create an AnthropicClient with mocked anthropic SDK."""
        # Mock the anthropic module before importing AnthropicClient
        mock_anthropic = MagicMock()
        mock_async_client = AsyncMock()
        mock_anthropic.AsyncAnthropic = lambda **_: mock_async_client

        with patch.dict(sys.modules, {"anthropic": mock_anthropic}):
            return AnthropicClient(
                config=ClientConfig(model="claude-3-sonnet-20240229")
            )

    def test_string_content_serialized(self) -> None:
        """String content converts to text block list."""
        client = self._make_client()
        msg = ChatMessage(role=Role.USER, content="hello")
        result = client._convert_message(msg)

        assert result["role"] == "user"
        assert result["content"] == [{"type": "text", "text": "hello"}]

    def test_multimodal_content_serialized(self) -> None:
        """Multimodal content serializes to Anthropic format."""
        client = self._make_client()
        msg = ChatMessage(
            role=Role.USER,
            content=[
                TextPart(text="describe"),
                ImageUrlPart(url="https://example.com/img.jpg"),
            ],
        )
        result = client._convert_message(msg)

        assert result["role"] == "user"
        assert len(result["content"]) == 2

        # Check text part
        assert result["content"][0] == {"type": "text", "text": "describe"}

        # Check image_url part in Anthropic format
        assert result["content"][1] == {
            "type": "image",
            "source": {"type": "url", "url": "https://example.com/img.jpg"},
        }

    def test_thinking_blocks_prepended(self) -> None:
        """Thinking blocks appear before serialized content."""
        client = self._make_client()
        thinking_block = {"type": "thinking", "thinking": "Let me think about this..."}
        msg = ChatMessage(
            role=Role.ASSISTANT,
            content="The answer is 42",
            thinking_blocks=[thinking_block],
        )
        result = client._convert_message(msg)

        assert result["role"] == "assistant"
        # Thinking block should be first, then the serialized text content
        assert len(result["content"]) == 2
        assert result["content"][0] == thinking_block
        assert result["content"][1] == {"type": "text", "text": "The answer is 42"}

    def test_thinking_blocks_with_multimodal_content(self) -> None:
        """Thinking blocks prepend to multimodal serialized content."""
        client = self._make_client()
        thinking_block = {"type": "thinking", "thinking": "Analyzing the image..."}
        msg = ChatMessage(
            role=Role.ASSISTANT,
            content=[
                TextPart(text="I see a cat"),
                ImageBase64Part(data="abc123", media_type="image/jpeg"),
            ],
            thinking_blocks=[thinking_block],
        )
        result = client._convert_message(msg)

        assert result["role"] == "assistant"
        assert len(result["content"]) == 3

        # Thinking block first
        assert result["content"][0] == thinking_block

        # Then text part
        assert result["content"][1] == {"type": "text", "text": "I see a cat"}

        # Then image part
        assert result["content"][2] == {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": "abc123",
            },
        }

    def test_empty_thinking_blocks_ignored(self) -> None:
        """Empty thinking_blocks list does not affect content structure."""
        client = self._make_client()
        msg = ChatMessage(
            role=Role.USER,
            content="hello",
            thinking_blocks=[],
        )
        result = client._convert_message(msg)

        assert result["role"] == "user"
        # Empty list is falsy, so should serialize normally
        assert result["content"] == [{"type": "text", "text": "hello"}]

    def test_thinking_blocks_with_empty_content(self) -> None:
        """Thinking blocks with empty content skips empty text block."""
        client = self._make_client()
        thinking_block = {"type": "thinking", "thinking": "Let me think..."}
        msg = ChatMessage(
            role=Role.ASSISTANT,
            content="",
            thinking_blocks=[thinking_block],
        )
        result = client._convert_message(msg)

        assert result["role"] == "assistant"
        # Should only contain the thinking block, no empty text block
        assert len(result["content"]) == 1
        assert result["content"][0] == thinking_block
