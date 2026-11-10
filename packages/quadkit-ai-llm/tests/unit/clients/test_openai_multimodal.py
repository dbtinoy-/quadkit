"""Test that OpenAI, Groq, and Mistral clients serialize MessageContent correctly."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.ai.llm.clients.groq import GroqClient
from quadkit.ai.llm.clients.mistral import MistralClient
from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.types import ChatMessage
from quadkit.contracts.ai.llm import Role
from quadkit.contracts.ai.multimodal import ImageUrlPart, TextPart


class TestOpenAIConvertMessage:
    """Verify OpenAI client correctly serializes multimodal content."""

    def _make_client(self):
        """Create a test OpenAI client instance with mocked openai module."""
        # Mock the openai module before importing OpenAIClient
        mock_openai = MagicMock()
        mock_async_client = AsyncMock()
        mock_openai.AsyncOpenAI = MagicMock(return_value=mock_async_client)

        with patch.dict(sys.modules, {"openai": mock_openai}):
            from quadkit.ai.llm.clients.openai import OpenAIClient

            config = ClientConfig(provider="openai", model="gpt-4-vision")
            return OpenAIClient(config)

    def test_string_content_passes_through(self) -> None:
        """Verify that plain string content is passed through unchanged."""
        client = self._make_client()
        msg = ChatMessage(role=Role.USER, content="hello")
        result = client._convert_message(msg)
        assert result["content"] == "hello"

    def test_multimodal_content_serialized(self) -> None:
        """Verify that multimodal content is properly serialized to OpenAI format."""
        client = self._make_client()
        msg = ChatMessage(
            role=Role.USER,
            content=[
                TextPart(text="describe this"),
                ImageUrlPart(url="https://example.com/img.jpg", detail="auto"),
            ],
        )
        result = client._convert_message(msg)
        assert isinstance(result["content"], list)
        assert result["content"][0] == {"type": "text", "text": "describe this"}
        assert result["content"][1] == {
            "type": "image_url",
            "image_url": {"url": "https://example.com/img.jpg", "detail": "auto"},
        }


class TestGroqSerializesContent:
    """Verify Groq client correctly serializes multimodal content."""

    def _make_client(self):
        """Create a test Groq client instance with mocked HTTP client."""
        config = ClientConfig(
            provider="groq",
            model="llama-3.1-70b-versatile",
            api_key="test-key-groq",
        )
        return GroqClient(config)

    @pytest.mark.asyncio
    async def test_multimodal_content_serialization_via_do_complete(self) -> None:
        """Verify that multimodal ChatMessage content is serialized in _do_complete.

        Tests the actual serialization path by calling _do_complete with
        multimodal content and verifying the serialized content is sent to
        the HTTP client.
        """
        msg = ChatMessage(
            role=Role.USER,
            content=[
                TextPart(text="analyze this image"),
                ImageUrlPart(url="https://example.com/image.jpg", detail="high"),
            ],
        )

        # Mock the HTTP client to capture the request
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "analyzed"}, "finish_reason": "stop"}],
            "model": "llama-3.1-70b-versatile",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)

        # Patch the ResilientHTTPClient at construction to inject our mock
        with patch(
            "quadkit.ai.llm.clients.groq.ResilientHTTPClient"
        ) as mock_client_class:
            mock_client_class.return_value = mock_http_client
            client = self._make_client()

            # Call _do_complete
            result = await client._do_complete([msg])

            # Verify the call succeeded
            assert result.is_ok()

            # Verify the HTTP client was called with serialized content
            mock_http_client.post.assert_called_once()
            call_args = mock_http_client.post.call_args

            # Extract the payload that was sent
            assert call_args is not None
            payload = call_args.kwargs.get("json")
            assert payload is not None

            # Verify the content was serialized correctly
            assert payload["messages"][0]["role"] == "user"
            assert isinstance(payload["messages"][0]["content"], list)
            assert payload["messages"][0]["content"][0] == {
                "type": "text",
                "text": "analyze this image",
            }
            assert payload["messages"][0]["content"][1] == {
                "type": "image_url",
                "image_url": {"url": "https://example.com/image.jpg", "detail": "high"},
            }


class TestMistralSerializesContent:
    """Verify Mistral client correctly serializes multimodal content."""

    def _make_client(self):
        """Create a test Mistral client instance with mocked HTTP client."""
        config = ClientConfig(
            provider="mistral",
            model="mistral-large-latest",
            api_key="test-key-mistral",
        )
        return MistralClient(config)

    @pytest.mark.asyncio
    async def test_multimodal_content_serialization_via_do_complete(self) -> None:
        """Verify that multimodal ChatMessage content is serialized in _do_complete.

        Tests the actual serialization path by calling _do_complete with
        multimodal content and verifying the serialized content is sent to
        the HTTP client.
        """
        msg = ChatMessage(
            role=Role.USER,
            content=[
                TextPart(text="what is in this image"),
                ImageUrlPart(url="https://example.com/photo.png", detail="low"),
            ],
        )

        # Mock the HTTP client to capture the request
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "analyzed"}, "finish_reason": "stop"}],
            "model": "mistral-large-latest",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
        mock_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.post = AsyncMock(return_value=mock_response)

        # Patch the ResilientHTTPClient at construction to inject our mock
        with patch(
            "quadkit.ai.llm.clients.mistral.ResilientHTTPClient"
        ) as mock_client_class:
            mock_client_class.return_value = mock_http_client
            client = self._make_client()

            # Call _do_complete
            result = await client._do_complete([msg])

            # Verify the call succeeded
            assert result.is_ok()

            # Verify the HTTP client was called with serialized content
            mock_http_client.post.assert_called_once()
            call_args = mock_http_client.post.call_args

            # Extract the payload that was sent
            assert call_args is not None
            payload = call_args.kwargs.get("json")
            assert payload is not None

            # Verify the content was serialized correctly
            assert payload["messages"][0]["role"] == "user"
            assert isinstance(payload["messages"][0]["content"], list)
            assert payload["messages"][0]["content"][0] == {
                "type": "text",
                "text": "what is in this image",
            }
            assert payload["messages"][0]["content"][1] == {
                "type": "image_url",
                "image_url": {"url": "https://example.com/photo.png", "detail": "low"},
            }
