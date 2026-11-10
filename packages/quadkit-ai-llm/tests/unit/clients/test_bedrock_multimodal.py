"""Test that Bedrock client handles MessageContent with image parts."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.ai.llm.clients.aws_bedrock import BedrockClient
from quadkit.ai.llm.config import ClientConfig
from quadkit.contracts.ai.multimodal import ImageBase64Part, ImageUrlPart, TextPart


class TestBedrockBuildContentBlocks:
    """Test Bedrock client _build_content_blocks method."""

    def _make_client(self) -> BedrockClient:
        """Create a BedrockClient with mocked boto3."""
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_boto3.client = MagicMock(return_value=mock_client)

        with patch.dict(sys.modules, {"boto3": mock_boto3, "botocore": MagicMock()}):
            return BedrockClient(
                config=ClientConfig(
                    model="anthropic.claude-3-sonnet", extra={"aws_region": "us-east-1"}
                )
            )

    @pytest.mark.asyncio
    async def test_string_content(self) -> None:
        """String content converts to single text block."""
        client = self._make_client()
        result = await client._build_content_blocks("hello")

        assert len(result) == 1
        assert result[0] == {"type": "text", "text": "hello"}

    @pytest.mark.asyncio
    async def test_text_part(self) -> None:
        """TextPart converts to text block."""
        client = self._make_client()
        result = await client._build_content_blocks([TextPart(text="hi")])

        assert len(result) == 1
        assert result[0] == {"type": "text", "text": "hi"}

    @pytest.mark.asyncio
    async def test_base64_image(self) -> None:
        """ImageBase64Part converts to Bedrock image block with camelCase mediaType."""
        client = self._make_client()
        result = await client._build_content_blocks(
            [ImageBase64Part(data="abc123", media_type="image/png")]
        )

        assert len(result) == 1
        assert result[0] == {
            "type": "image",
            "source": {
                "type": "base64",
                "mediaType": "image/png",
                "data": "abc123",
            },
        }

    @pytest.mark.asyncio
    async def test_url_image_prefetched(self) -> None:
        """ImageUrlPart triggers fetcher, result serialized as base64 block."""
        client = self._make_client()

        # Mock fetch_image_as_base64
        mock_fetcher = AsyncMock(
            return_value=ImageBase64Part(data="fetched_b64", media_type="image/jpeg")
        )

        with patch(
            "quadkit.ai.llm.clients.aws_bedrock.fetch_image_as_base64",
            mock_fetcher,
        ):
            result = await client._build_content_blocks(
                [ImageUrlPart(url="https://example.com/img.jpg")]
            )

        # Verify fetcher was called
        mock_fetcher.assert_called_once_with("https://example.com/img.jpg")

        # Check serialized result
        assert len(result) == 1
        assert result[0] == {
            "type": "image",
            "source": {
                "type": "base64",
                "mediaType": "image/jpeg",
                "data": "fetched_b64",
            },
        }

    @pytest.mark.asyncio
    async def test_mixed_content(self) -> None:
        """Mixed TextPart and ImageBase64Part serialize correctly."""
        client = self._make_client()
        result = await client._build_content_blocks(
            [
                TextPart(text="Look at this"),
                ImageBase64Part(data="img_data", media_type="image/png"),
            ]
        )

        assert len(result) == 2
        assert result[0] == {"type": "text", "text": "Look at this"}
        assert result[1] == {
            "type": "image",
            "source": {
                "type": "base64",
                "mediaType": "image/png",
                "data": "img_data",
            },
        }

    @pytest.mark.asyncio
    async def test_empty_list(self) -> None:
        """Empty content list returns empty block list."""
        client = self._make_client()
        result = await client._build_content_blocks([])

        assert result == []

    @pytest.mark.asyncio
    async def test_multiple_images(self) -> None:
        """Multiple image parts fetch and serialize independently."""
        client = self._make_client()

        # Create a fetcher that returns different data for each call
        fetched_parts = [
            ImageBase64Part(data="b64_1", media_type="image/jpeg"),
            ImageBase64Part(data="b64_2", media_type="image/png"),
        ]
        mock_fetcher = AsyncMock(side_effect=fetched_parts)

        with patch(
            "quadkit.ai.llm.clients.aws_bedrock.fetch_image_as_base64",
            mock_fetcher,
        ):
            result = await client._build_content_blocks(
                [
                    ImageUrlPart(url="https://example.com/img1.jpg"),
                    ImageUrlPart(url="https://example.com/img2.png"),
                ]
            )

        # Verify fetcher called twice
        assert mock_fetcher.call_count == 2

        # Check results
        assert len(result) == 2
        assert result[0] == {
            "type": "image",
            "source": {
                "type": "base64",
                "mediaType": "image/jpeg",
                "data": "b64_1",
            },
        }
        assert result[1] == {
            "type": "image",
            "source": {
                "type": "base64",
                "mediaType": "image/png",
                "data": "b64_2",
            },
        }
