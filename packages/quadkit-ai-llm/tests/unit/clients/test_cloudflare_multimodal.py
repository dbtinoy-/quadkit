"""Test that Cloudflare Workers AI client handles MessageContent with text-only serialization."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from quadkit.ai.llm.clients.cloudflare_workers import (
    _convert_messages_for_cloudflare,
)
from quadkit.ai.llm.types import ChatMessage
from quadkit.contracts.ai.llm import Role
from quadkit.contracts.ai.multimodal import ImageBase64Part, ImageUrlPart, TextPart


class TestCloudflareMultimodalMessageSerialization:
    """Test Cloudflare client multimodal message serialization via serialize_text_only."""

    def test_string_content_passes_through_unchanged(self) -> None:
        """String content in messages is preserved unchanged."""
        messages = [ChatMessage(role=Role.USER, content="hello world")]

        # The _convert_messages_for_cloudflare function should preserve string content
        with patch(
            "quadkit.ai.llm.clients.cloudflare_workers.serialize_text_only",
            return_value="hello world",
        ) as mock_serialize:
            result = _convert_messages_for_cloudflare(messages)
            assert len(result) == 1
            assert result[0]["role"] == "user"
            assert result[0]["content"] == "hello world"
            mock_serialize.assert_called_once()

    def test_text_parts_list_extracted_to_text(self) -> None:
        """List with TextPart entries is extracted to plain text."""
        # Create ChatMessage with multimodal content
        messages = [
            ChatMessage(
                role=Role.USER,
                content=[
                    TextPart(text="hello"),
                    TextPart(text="world"),
                ],
            )
        ]

        with patch(
            "quadkit.ai.llm.clients.cloudflare_workers.serialize_text_only",
            return_value="hello world",
        ) as mock_serialize:
            result = _convert_messages_for_cloudflare(messages)
            assert len(result) == 1
            assert result[0]["role"] == "user"
            assert result[0]["content"] == "hello world"
            mock_serialize.assert_called_once()

    def test_image_url_part_logged_and_skipped(self) -> None:
        """ImageUrlPart in message list is skipped and warning is logged."""
        messages = [
            ChatMessage(
                role=Role.USER,
                content=[
                    TextPart(text="describe this"),
                    ImageUrlPart(url="https://example.com/img.jpg"),
                ],
            )
        ]

        mock_logger = MagicMock()
        with patch("quadkit.ai.llm.clients.cloudflare_workers.logger", mock_logger):
            result = _convert_messages_for_cloudflare(messages)
            assert len(result) == 1
            assert result[0]["role"] == "user"
            # The image part should be skipped, text extracted
            assert result[0]["content"] == "describe this"
            # Assert logger.warning was called for the image part
            mock_logger.warning.assert_called_once()

    def test_multimodal_content_union_type_handled(self) -> None:
        """MessageContent union type (str | list[ContentPart]) is properly handled."""

        # Test string content
        messages_str = [ChatMessage(role=Role.USER, content="plain text")]

        # Test list content
        messages_list = [
            ChatMessage(
                role=Role.USER,
                content=[TextPart(text="from list")],
            )
        ]

        # Both should work without errors
        with patch(
            "quadkit.ai.llm.clients.cloudflare_workers.serialize_text_only",
            return_value="plain text",
        ) as mock_serialize_str:
            result_str = _convert_messages_for_cloudflare(messages_str)
            assert result_str[0]["content"] == "plain text"
            mock_serialize_str.assert_called_once()

        with patch(
            "quadkit.ai.llm.clients.cloudflare_workers.serialize_text_only",
            return_value="from list",
        ) as mock_serialize_list:
            result_list = _convert_messages_for_cloudflare(messages_list)
            assert result_list[0]["content"] == "from list"
            mock_serialize_list.assert_called_once()

    def test_base64_image_part_logged_and_skipped(self) -> None:
        """ImageBase64Part in message list is skipped and warning is logged."""
        messages = [
            ChatMessage(
                role=Role.USER,
                content=[
                    TextPart(text="caption"),
                    ImageBase64Part(data="abc123", media_type="image/png"),
                ],
            )
        ]

        mock_logger = MagicMock()
        with patch("quadkit.ai.llm.clients.cloudflare_workers.logger", mock_logger):
            result = _convert_messages_for_cloudflare(messages)
            assert len(result) == 1
            assert result[0]["role"] == "user"
            # The image part should be skipped
            assert result[0]["content"] == "caption"
            # Assert logger.warning was called for the image part
            mock_logger.warning.assert_called_once()
