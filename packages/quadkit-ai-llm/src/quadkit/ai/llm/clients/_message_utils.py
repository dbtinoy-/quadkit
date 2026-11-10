"""Per-provider serializers for ``MessageContent`` → wire-format dicts.

Each function converts a ``MessageContent`` value (either a plain ``str`` or
a ``list[ContentPart]``) into the format expected by that provider's API.
These are pure sync functions; clients that need to fetch image URLs before
serializing should call ``fetch_image_as_base64`` from ``quadkit.ai.llm.multimodal``
first and replace ``ImageUrlPart`` entries with the resulting ``ImageBase64Part``.
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.ai.multimodal import (
    ImageBase64Part,
    ImageUrlPart,
    MessageContent,
    TextPart,
)


def serialize_content_for_openai(
    content: MessageContent | None,
) -> str | list[dict[str, Any]]:
    """Serialize ``MessageContent`` to the OpenAI content wire format.

    - Plain ``str`` → returned unchanged.
    - ``list[ContentPart]`` → list of OpenAI-typed dicts.
    - ``ImageUrlPart`` → ``{"type": "image_url", "image_url": {"url": ..., "detail": ...}}``.
    - ``ImageBase64Part`` → encoded as ``data:<mime>;base64,<data>`` URL.

    Args:
        content: Message content to serialize.  ``None`` (assistant turns
            that only carry tool calls) serializes to an empty string.

    Returns:
        String or list of OpenAI content dicts.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content

    parts: list[dict[str, Any]] = []
    for part in content:
        if isinstance(part, TextPart):
            parts.append({"type": "text", "text": part.text})
        elif isinstance(part, ImageUrlPart):
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": part.url, "detail": part.detail},
                }
            )
        elif isinstance(part, ImageBase64Part):
            data_uri = f"data:{part.media_type};base64,{part.data}"
            parts.append(
                {
                    "type": "image_url",
                    "image_url": {"url": data_uri, "detail": "auto"},
                }
            )
    return parts


def serialize_content_for_anthropic(
    content: MessageContent,
) -> list[dict[str, Any]]:
    """Serialize ``MessageContent`` to the Anthropic content block format.

    Anthropic always wants a list of typed blocks, even for plain text.

    - ``str`` → ``[{"type": "text", "text": ...}]``
    - ``ImageUrlPart`` → ``{"type": "image", "source": {"type": "url", "url": ...}}``
    - ``ImageBase64Part`` → ``{"type": "image", "source": {"type": "base64", ...}}``

    Args:
        content: Message content to serialize.

    Returns:
        List of Anthropic content blocks.
    """
    if isinstance(content, str):
        return [{"type": "text", "text": content}]

    blocks: list[dict[str, Any]] = []
    for part in content:
        if isinstance(part, TextPart):
            blocks.append({"type": "text", "text": part.text})
        elif isinstance(part, ImageUrlPart):
            blocks.append(
                {
                    "type": "image",
                    "source": {"type": "url", "url": part.url},
                }
            )
        elif isinstance(part, ImageBase64Part):
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": part.media_type,
                        "data": part.data,
                    },
                }
            )
    return blocks


def serialize_content_for_gemini(
    content: MessageContent | None,
) -> list[dict[str, Any]]:
    """Serialize ``MessageContent`` to Gemini content part format.

    - ``str`` → ``[{"text": ...}]``
    - ``ImageUrlPart`` → ``{"file_data": {"mime_type": ..., "file_uri": url}}``
    - ``ImageBase64Part`` → ``{"inline_data": {"mime_type": ..., "data": base64}}``

    Gemini supports HTTP/HTTPS URLs directly via ``file_uri`` (Gemini 1.5+).

    Args:
        content: Message content to serialize.  ``None`` (assistant turns
            that only carry tool calls) yields an empty parts list.

    Returns:
        List of Gemini content part dicts.
    """
    if content is None:
        return []
    if isinstance(content, str):
        return [{"text": content}]

    parts: list[dict[str, Any]] = []
    for part in content:
        if isinstance(part, TextPart):
            parts.append({"text": part.text})
        elif isinstance(part, ImageUrlPart):
            mime = _guess_mime_from_url(part.url)
            parts.append({"file_data": {"mime_type": mime, "file_uri": part.url}})
        elif isinstance(part, ImageBase64Part):
            parts.append(
                {"inline_data": {"mime_type": part.media_type, "data": part.data}}
            )
    return parts


def serialize_text_for_ollama(content: MessageContent) -> tuple[str, list[str]]:
    """Serialize ``MessageContent`` to Ollama's ``(text, images)`` format.

    Ollama uses ``content`` (text) + ``images`` (list of raw base64 strings,
    no ``data:`` prefix).

    - ``str`` → ``(str, [])``
    - ``TextPart`` → text is concatenated
    - ``ImageBase64Part`` → appended to ``images`` list
    - ``ImageUrlPart`` → callers must pre-fetch via ``fetch_image_as_base64``;
      a ``[image: <url>]`` placeholder is inserted into text so the content
      is not silently dropped.

    Args:
        content: Message content to serialize.

    Returns:
        Tuple of (text_content, base64_images_list).
    """
    if isinstance(content, str):
        return content, []

    text_parts: list[str] = []
    images: list[str] = []
    for part in content:
        if isinstance(part, TextPart):
            text_parts.append(part.text)
        elif isinstance(part, ImageBase64Part):
            images.append(part.data)
        elif isinstance(part, ImageUrlPart):
            text_parts.append(f"[image: {part.url}]")
    return " ".join(text_parts), images


def serialize_text_only(
    content: MessageContent | None,
    *,
    logger: Any,
    client_name: str,
) -> str:
    """Extract text from ``MessageContent``, warning on image parts.

    For clients that do not support vision. Image parts produce a structured
    warning log and are excluded from the returned text.

    Args:
        content: MessageContent to extract text from.  ``None`` (assistant
            turns that only carry tool calls) yields an empty string.
        logger: structlog logger instance (must have ``.warning()``).
        client_name: Client name for warning context (e.g. ``"cloudflare"``).

    Returns:
        Plain text string with image parts omitted.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content

    texts: list[str] = []
    for part in content:
        if isinstance(part, TextPart):
            texts.append(part.text)
        elif isinstance(part, (ImageUrlPart, ImageBase64Part)):
            logger.warning(
                "multimodal_image_dropped",
                client=client_name,
                reason="client does not support vision",
                part_type=part.type,
            )
    return " ".join(texts)


def _guess_mime_from_url(url: str) -> str:
    """Guess image MIME type from URL file extension.

    Args:
        url: Image URL.

    Returns:
        MIME type string, defaulting to ``"image/jpeg"``.
    """
    lower = url.lower().split("?")[0]
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".gif"):
        return "image/gif"
    if lower.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"
