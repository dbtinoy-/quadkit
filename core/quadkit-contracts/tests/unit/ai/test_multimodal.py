"""Tests for multimodal message content types."""

from __future__ import annotations


def test_text_part_has_required_fields() -> None:
    from quadkit.contracts.ai.multimodal import TextPart

    part = TextPart(text="hello")
    assert part.text == "hello"
    assert part.type == "text"


def test_image_url_part_has_required_fields() -> None:
    from quadkit.contracts.ai.multimodal import ImageUrlPart

    part = ImageUrlPart(url="https://example.com/img.jpg")
    assert part.url == "https://example.com/img.jpg"
    assert part.type == "image_url"
    assert part.detail == "auto"


def test_image_base64_part_has_required_fields() -> None:
    from quadkit.contracts.ai.multimodal import ImageBase64Part

    part = ImageBase64Part(data="abc123", media_type="image/jpeg")
    assert part.data == "abc123"
    assert part.media_type == "image/jpeg"
    assert part.type == "image_base64"


def test_message_content_type_alias() -> None:
    from quadkit.contracts.ai.multimodal import (
        ImageUrlPart,
        MessageContent,
        TextPart,
    )

    content_str: MessageContent = "plain text"
    content_list: MessageContent = [
        TextPart(text="hello"),
        ImageUrlPart(url="https://example.com/img.jpg"),
    ]
    assert isinstance(content_str, str)
    assert isinstance(content_list, list)
    assert isinstance(content_list[0], TextPart)
    assert isinstance(content_list[1], ImageUrlPart)


def test_types_exported_from_contracts_ai() -> None:
    from quadkit.contracts.ai import (
        ContentPart,
        ImageBase64Part,
        ImageUrlPart,
        MessageContent,
        TextPart,
    )

    assert TextPart is not None
    assert ImageUrlPart is not None
    assert ImageBase64Part is not None
    assert ContentPart is not None
    assert MessageContent is not None
