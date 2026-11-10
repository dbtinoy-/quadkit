"""Async image fetcher that converts URLs to base64-encoded image parts."""

from __future__ import annotations

import base64

import httpx

from quadkit.ai.llm.exceptions import LLMError
from quadkit.contracts.ai.multimodal import ImageBase64Part
from quadkit.logging import (
    get_logger,
    safe_error_type,
)

logger = get_logger(__name__)


async def fetch_image_as_base64(url: str, timeout: float = 10.0) -> ImageBase64Part:
    """Fetch an image URL and return it as a base64-encoded part.

    Used by clients that cannot pass image URLs through to the provider
    (e.g. Ollama, AWS Bedrock). The fetch is done once per message
    construction — callers should cache results when sending the same
    image in multiple turns.

    Args:
        url: Public HTTP/HTTPS URL of the image.
        timeout: Request timeout in seconds (default: 10).

    Returns:
        :class:`~quadkit.contracts.ai.multimodal.ImageBase64Part` with
        base64-encoded data and detected media type.

    Raises:
        LLMError: If the HTTP request fails or times out.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise LLMError(f"Failed to fetch image ({safe_error_type(exc)})") from None

    raw = response.content
    media_type = (
        response.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    )
    if not media_type.startswith("image/"):
        media_type = "image/jpeg"

    logger.debug("image_fetched", media_type=media_type, size_bytes=len(raw))
    return ImageBase64Part(
        data=base64.b64encode(raw).decode(),
        media_type=media_type,
    )
