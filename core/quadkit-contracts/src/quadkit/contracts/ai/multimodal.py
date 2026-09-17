"""Typed multimodal message content parts for cross-client LLM messaging."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias


@dataclass(frozen=True)
class TextPart:
    """A plain-text content part in a multimodal message.

    Attributes:
        text: The text content.
        type: Discriminator field, always ``"text"``.
    """

    text: str
    type: Literal["text"] = field(default="text", init=False)


@dataclass(frozen=True)
class ImageUrlPart:
    """An image specified by URL in a multimodal message.

    The framework passes the URL through to providers that support it
    natively (OpenAI, Anthropic, Gemini). For providers that require
    base64 (Ollama, Bedrock), the client fetches and converts.

    Attributes:
        url: Public or data-URI URL of the image.
        detail: OpenAI vision detail level (``"auto"``, ``"low"``, ``"high"``).
        type: Discriminator field, always ``"image_url"``.
    """

    url: str
    detail: Literal["auto", "low", "high"] = "auto"
    type: Literal["image_url"] = field(default="image_url", init=False)


@dataclass(frozen=True)
class ImageBase64Part:
    """An image pre-encoded as base64 in a multimodal message.

    Attributes:
        data: Raw base64-encoded bytes (no ``data:`` prefix).
        media_type: MIME type, e.g. ``"image/jpeg"``.
        detail: OpenAI vision detail level, or ``""`` when the source
            carries none (e.g. Claude-sourced images).
        type: Discriminator field, always ``"image_base64"``.
    """

    data: str
    media_type: str
    detail: str = ""
    type: Literal["image_base64"] = field(default="image_base64", init=False)


ContentPart: TypeAlias = TextPart | ImageUrlPart | ImageBase64Part
"""Union of all supported content part types."""

MessageContent: TypeAlias = str | list[ContentPart]
"""Content field type for ``ChatMessage``.

Either a plain string (backward-compatible) or a list of typed parts
for multimodal messages.
"""


__all__ = [
    "ContentPart",
    "ImageBase64Part",
    "ImageUrlPart",
    "MessageContent",
    "TextPart",
]
