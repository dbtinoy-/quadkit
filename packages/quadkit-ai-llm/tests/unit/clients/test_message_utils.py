"""Tests for per-provider MessageContent serializers."""

from __future__ import annotations

from quadkit.contracts.ai.multimodal import ImageBase64Part, ImageUrlPart, TextPart


class TestSerializeContentForOpenAI:
    def test_string_content_returned_unchanged(self) -> None:
        from quadkit.ai.llm.clients._message_utils import serialize_content_for_openai

        result = serialize_content_for_openai("hello world")
        assert result == "hello world"

    def test_text_only_list_becomes_content_blocks(self) -> None:
        from quadkit.ai.llm.clients._message_utils import serialize_content_for_openai

        result = serialize_content_for_openai([TextPart(text="hello")])
        assert result == [{"type": "text", "text": "hello"}]

    def test_image_url_part_serialized(self) -> None:
        from quadkit.ai.llm.clients._message_utils import serialize_content_for_openai

        result = serialize_content_for_openai(
            [
                TextPart(text="describe"),
                ImageUrlPart(url="https://example.com/cat.jpg", detail="high"),
            ]
        )
        assert result == [
            {"type": "text", "text": "describe"},
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/cat.jpg", "detail": "high"},
            },
        ]

    def test_image_base64_part_serialized_as_data_uri(self) -> None:
        from quadkit.ai.llm.clients._message_utils import serialize_content_for_openai

        result = serialize_content_for_openai(
            [
                ImageBase64Part(data="abc123", media_type="image/png"),
            ]
        )
        assert result == [
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64,abc123", "detail": "auto"},
            },
        ]


class TestSerializeContentForAnthropic:
    def test_string_content_returns_text_block_list(self) -> None:
        from quadkit.ai.llm.clients._message_utils import (
            serialize_content_for_anthropic,
        )

        result = serialize_content_for_anthropic("hello")
        assert result == [{"type": "text", "text": "hello"}]

    def test_image_url_part_uses_url_source(self) -> None:
        from quadkit.ai.llm.clients._message_utils import (
            serialize_content_for_anthropic,
        )

        result = serialize_content_for_anthropic(
            [
                TextPart(text="what is this?"),
                ImageUrlPart(url="https://example.com/img.jpg"),
            ]
        )
        assert result == [
            {"type": "text", "text": "what is this?"},
            {
                "type": "image",
                "source": {"type": "url", "url": "https://example.com/img.jpg"},
            },
        ]

    def test_image_base64_part_uses_base64_source(self) -> None:
        from quadkit.ai.llm.clients._message_utils import (
            serialize_content_for_anthropic,
        )

        result = serialize_content_for_anthropic(
            [
                ImageBase64Part(data="abc123", media_type="image/jpeg"),
            ]
        )
        assert result == [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": "abc123",
                },
            },
        ]


class TestSerializeContentForGemini:
    def test_string_returns_text_part(self) -> None:
        from quadkit.ai.llm.clients._message_utils import serialize_content_for_gemini

        result = serialize_content_for_gemini("hello gemini")
        assert result == [{"text": "hello gemini"}]

    def test_image_url_part_returns_file_data(self) -> None:
        from quadkit.ai.llm.clients._message_utils import serialize_content_for_gemini

        result = serialize_content_for_gemini(
            [
                TextPart(text="describe"),
                ImageUrlPart(url="https://example.com/image.jpg"),
            ]
        )
        assert result == [
            {"text": "describe"},
            {
                "file_data": {
                    "mime_type": "image/jpeg",
                    "file_uri": "https://example.com/image.jpg",
                }
            },
        ]

    def test_image_base64_returns_inline_data(self) -> None:
        from quadkit.ai.llm.clients._message_utils import serialize_content_for_gemini

        result = serialize_content_for_gemini(
            [
                ImageBase64Part(data="abc123", media_type="image/png"),
            ]
        )
        assert result == [
            {"inline_data": {"mime_type": "image/png", "data": "abc123"}},
        ]

    def test_image_url_guess_mime_png(self) -> None:
        from quadkit.ai.llm.clients._message_utils import serialize_content_for_gemini

        result = serialize_content_for_gemini(
            [ImageUrlPart(url="https://example.com/img.png")]
        )
        assert result == [
            {
                "file_data": {
                    "mime_type": "image/png",
                    "file_uri": "https://example.com/img.png",
                }
            }
        ]

    def test_image_url_guess_mime_strips_query_string(self) -> None:
        from quadkit.ai.llm.clients._message_utils import serialize_content_for_gemini

        # MIME is detected from extension (before ?), but file_uri preserves the original URL
        result = serialize_content_for_gemini(
            [ImageUrlPart(url="https://cdn.example.com/photo.webp?v=3")]
        )
        assert result == [
            {
                "file_data": {
                    "mime_type": "image/webp",
                    "file_uri": "https://cdn.example.com/photo.webp?v=3",
                }
            }
        ]

    def test_image_url_guess_mime_gif(self) -> None:
        from quadkit.ai.llm.clients._message_utils import serialize_content_for_gemini

        result = serialize_content_for_gemini(
            [ImageUrlPart(url="https://example.com/anim.gif")]
        )
        assert result == [
            {
                "file_data": {
                    "mime_type": "image/gif",
                    "file_uri": "https://example.com/anim.gif",
                }
            }
        ]


class TestSerializeTextForOllama:
    def test_string_returns_text_and_no_images(self) -> None:
        from quadkit.ai.llm.clients._message_utils import serialize_text_for_ollama

        text, images = serialize_text_for_ollama("hello")
        assert text == "hello"
        assert images == []

    def test_text_part_extracted(self) -> None:
        from quadkit.ai.llm.clients._message_utils import serialize_text_for_ollama

        text, images = serialize_text_for_ollama([TextPart(text="hello")])
        assert text == "hello"
        assert images == []

    def test_base64_image_collected_separately(self) -> None:
        from quadkit.ai.llm.clients._message_utils import serialize_text_for_ollama

        text, images = serialize_text_for_ollama(
            [
                TextPart(text="describe"),
                ImageBase64Part(data="abc123", media_type="image/jpeg"),
            ]
        )
        assert text == "describe"
        assert images == ["abc123"]

    def test_url_image_left_as_placeholder(self) -> None:
        """URL images in Ollama produce placeholder — callers must pre-fetch."""
        from quadkit.ai.llm.clients._message_utils import serialize_text_for_ollama

        text, images = serialize_text_for_ollama(
            [
                TextPart(text="describe"),
                ImageUrlPart(url="https://example.com/img.jpg"),
            ]
        )
        assert "[image: https://example.com/img.jpg]" in text
        assert images == []

    def test_multiple_text_parts_are_joined_with_space(self) -> None:
        from quadkit.ai.llm.clients._message_utils import serialize_text_for_ollama

        text, images = serialize_text_for_ollama(
            [
                TextPart(text="first"),
                TextPart(text="second"),
            ]
        )
        assert text == "first second"
        assert images == []


class TestSerializeTextOnly:
    def test_string_passes_through(self) -> None:
        from unittest.mock import MagicMock

        from quadkit.ai.llm.clients._message_utils import serialize_text_only

        mock_logger = MagicMock()
        result = serialize_text_only("hello", logger=mock_logger, client_name="test")
        assert result == "hello"
        mock_logger.warning.assert_not_called()

    def test_text_parts_joined(self) -> None:
        from unittest.mock import MagicMock

        from quadkit.ai.llm.clients._message_utils import serialize_text_only

        mock_logger = MagicMock()
        result = serialize_text_only(
            [TextPart(text="hello"), TextPart(text="world")],
            logger=mock_logger,
            client_name="test",
        )
        assert result == "hello world"

    def test_image_parts_warn_and_are_dropped(self) -> None:
        from unittest.mock import MagicMock

        from quadkit.ai.llm.clients._message_utils import serialize_text_only

        mock_logger = MagicMock()
        result = serialize_text_only(
            [TextPart(text="text"), ImageUrlPart(url="https://example.com/img.jpg")],
            logger=mock_logger,
            client_name="cloudflare",
        )
        assert result == "text"
        mock_logger.warning.assert_called_once_with(
            "multimodal_image_dropped",
            client="cloudflare",
            reason="client does not support vision",
            part_type="image_url",
        )

    def test_base64_image_part_warns_and_is_dropped(self) -> None:
        from unittest.mock import MagicMock

        from quadkit.ai.llm.clients._message_utils import serialize_text_only

        mock_logger = MagicMock()
        result = serialize_text_only(
            [
                TextPart(text="caption"),
                ImageBase64Part(data="abc123", media_type="image/png"),
            ],
            logger=mock_logger,
            client_name="cohere",
        )
        assert result == "caption"
        mock_logger.warning.assert_called_once_with(
            "multimodal_image_dropped",
            client="cohere",
            reason="client does not support vision",
            part_type="image_base64",
        )
