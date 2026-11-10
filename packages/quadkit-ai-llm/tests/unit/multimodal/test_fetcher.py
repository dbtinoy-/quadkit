"""Tests for the async image URL fetcher."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from quadkit.ai.llm.exceptions import LLMError
from quadkit.ai.llm.multimodal.fetcher import fetch_image_as_base64
from quadkit.contracts.ai.multimodal import ImageBase64Part

_PRIVATE_IMAGE_URL = "https://private.example/tenant-42/image?token=private-token"


class TestFetchImageAsBase64:
    @pytest.mark.asyncio
    async def test_returns_image_base64_part(self) -> None:
        raw_bytes = b"\xff\xd8\xff\xe0fake_jpeg_bytes"
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.content = raw_bytes
        mock_response.headers = {"content-type": "image/jpeg"}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("quadkit.ai.llm.multimodal.fetcher.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_image_as_base64("https://example.com/img.jpg")

        assert isinstance(result, ImageBase64Part)
        assert result.media_type == "image/jpeg"
        assert result.data == base64.b64encode(raw_bytes).decode()

    @pytest.mark.asyncio
    async def test_defaults_to_jpeg_when_no_content_type(self) -> None:
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.content = b"fakebytes"
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("quadkit.ai.llm.multimodal.fetcher.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_image_as_base64("https://example.com/noext")

        assert result.media_type == "image/jpeg"
        assert isinstance(result, ImageBase64Part)
        assert result.data == base64.b64encode(b"fakebytes").decode()

    @pytest.mark.asyncio
    async def test_raises_llm_error_on_http_failure(self) -> None:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "404", request=MagicMock(), response=MagicMock()
        ))

        with patch("quadkit.ai.llm.multimodal.fetcher.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(LLMError) as exc_info:
                await fetch_image_as_base64(_PRIVATE_IMAGE_URL)
        assert "Failed to fetch image (HTTPStatusError)" in str(exc_info.value)
        assert _PRIVATE_IMAGE_URL not in str(exc_info.value)
        assert "private-token" not in str(exc_info.value)
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__suppress_context__ is True

    @pytest.mark.asyncio
    async def test_raises_llm_error_on_http_status_error(self) -> None:
        """Verify 4xx/5xx responses raise LLMError."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "403 Forbidden", request=MagicMock(), response=MagicMock()
        )

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("quadkit.ai.llm.multimodal.fetcher.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(LLMError) as exc_info:
                await fetch_image_as_base64(_PRIVATE_IMAGE_URL)
        assert "Failed to fetch image (HTTPStatusError)" in str(exc_info.value)
        assert _PRIVATE_IMAGE_URL not in str(exc_info.value)
        assert "private-token" not in str(exc_info.value)
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__suppress_context__ is True

    @pytest.mark.asyncio
    async def test_strips_charset_from_content_type(self) -> None:
        """Verify charset suffix is stripped: 'image/png; charset=utf-8' → 'image/png'."""
        raw = b"pngdata"
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"content-type": "image/png; charset=utf-8"}
        mock_response.content = raw

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("quadkit.ai.llm.multimodal.fetcher.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_image_as_base64("https://example.com/image.png")

        assert isinstance(result, ImageBase64Part)
        assert result.media_type == "image/png"
        assert result.data == base64.b64encode(raw).decode()

    @pytest.mark.asyncio
    async def test_defaults_to_jpeg_when_content_type_is_not_image(self) -> None:
        """Verify non-image content-type (e.g. text/html) falls back to image/jpeg."""
        raw = b"binarydata"
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.content = raw

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("quadkit.ai.llm.multimodal.fetcher.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_image_as_base64("https://example.com/image")

        assert isinstance(result, ImageBase64Part)
        assert result.media_type == "image/jpeg"
        assert result.data == base64.b64encode(raw).decode()

    @pytest.mark.asyncio
    async def test_raises_llm_error_on_timeout(self) -> None:
        """Verify timeout raises LLMError."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(
            side_effect=httpx.TimeoutException("timed out", request=MagicMock())
        )

        with patch("quadkit.ai.llm.multimodal.fetcher.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(LLMError) as exc_info:
                await fetch_image_as_base64(_PRIVATE_IMAGE_URL, timeout=0.001)
        assert "Failed to fetch image (TimeoutException)" in str(exc_info.value)
        assert _PRIVATE_IMAGE_URL not in str(exc_info.value)
        assert "private-token" not in str(exc_info.value)
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__suppress_context__ is True

