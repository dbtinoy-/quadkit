"""Test that Ollama client handles MessageContent with image parts."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.types import ChatMessage
from quadkit.contracts.ai.llm import Role
from quadkit.contracts.ai.multimodal import ImageBase64Part, ImageUrlPart, TextPart


class TestOllamaSerializeMessages:
    def _make_client(self):
        # Mock the ollama module before importing OllamaClient
        mock_ollama = MagicMock()
        mock_async_client = AsyncMock()
        mock_ollama.AsyncClient = lambda **_: mock_async_client

        with patch.dict(sys.modules, {"ollama": mock_ollama}):
            from quadkit.ai.llm.clients.ollama import OllamaClient

            return OllamaClient(
                config=ClientConfig(model="llama3", api_base="http://localhost:11434")
            )

    @pytest.mark.asyncio
    async def test_string_content_produces_no_images(self) -> None:
        client = self._make_client()
        msg = ChatMessage(role=Role.USER, content="hello")
        result = await client._serialize_messages_for_ollama([msg])
        assert result[0]["content"] == "hello"
        assert "images" not in result[0]

    @pytest.mark.asyncio
    async def test_base64_image_adds_images_key(self) -> None:
        client = self._make_client()
        msg = ChatMessage(
            role=Role.USER,
            content=[
                TextPart(text="describe"),
                ImageBase64Part(data="abc123", media_type="image/jpeg"),
            ],
        )
        result = await client._serialize_messages_for_ollama([msg])
        assert result[0]["content"] == "describe"
        assert result[0]["images"] == ["abc123"]

    @pytest.mark.asyncio
    async def test_url_image_is_fetched_and_converted(self) -> None:
        # Pre-import the ollama module with the mock
        mock_ollama = MagicMock()
        mock_async_client = AsyncMock()
        mock_ollama.AsyncClient = lambda **_: mock_async_client

        fetched = ImageBase64Part(data="fetchedbase64", media_type="image/jpeg")

        with patch.dict(sys.modules, {"ollama": mock_ollama}):
            # Import inside the patch so the OllamaClient binding is fresh
            from quadkit.ai.llm.clients import ollama as ollama_module

            client = ollama_module.OllamaClient(
                config=ClientConfig(model="llama3", api_base="http://localhost:11434")
            )

            msg = ChatMessage(
                role=Role.USER,
                content=[
                    TextPart(text="what is this?"),
                    ImageUrlPart(url="https://example.com/img.jpg"),
                ],
            )

            # Patch the function inside ollama_module
            with patch.object(
                ollama_module, "fetch_image_as_base64", AsyncMock(return_value=fetched)
            ):
                result = await client._serialize_messages_for_ollama([msg])

            assert result[0]["content"] == "what is this?"
            assert result[0]["images"] == ["fetchedbase64"]
