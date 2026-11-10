"""Test that Cohere client handles MessageContent with text-only serialization."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from quadkit.ai.llm.clients.cohere import CohereClient
from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.types import ChatMessage
from quadkit.contracts.ai.llm import Role
from quadkit.contracts.ai.multimodal import ImageBase64Part, ImageUrlPart, TextPart


class TestCohereMultimodalMessageSerialization:
    """Test Cohere client multimodal message serialization via serialize_text_only."""

    def _make_client(self) -> CohereClient:
        """Create a CohereClient with necessary config."""
        return CohereClient(
            config=ClientConfig(
                model="command-r-plus",
                api_key="test-api-key",
            )
        )

    def test_string_content_passes_through_unchanged(self) -> None:
        """String content in messages is preserved unchanged."""
        client = self._make_client()

        # Test the _build_payload method which processes messages
        # Cohere expects messages to be converted to user_message and chat_history
        messages = [ChatMessage(role=Role.USER, content="hello world")]

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            with patch(
                "quadkit.ai.llm.clients._cohere_mappers.serialize_text_only",
                return_value="hello world",
            ) as mock_serialize:
                _http_client, payload, _model = client._build_payload(
                    messages, stream=False, kwargs={}
                )

                # The payload should contain the user_message extracted from content
                assert payload["message"] == "hello world"
                mock_serialize.assert_called_once()

    def test_text_parts_list_extracted_to_text(self) -> None:
        """List with TextPart entries is extracted to plain text."""
        client = self._make_client()
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

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            with patch(
                "quadkit.ai.llm.clients._cohere_mappers.serialize_text_only",
                return_value="hello world",
            ) as mock_serialize:
                _http_client, payload, _model = client._build_payload(
                    messages, stream=False, kwargs={}
                )

                # The text parts should be joined
                assert payload["message"] == "hello world"
                mock_serialize.assert_called_once()

    def test_image_url_part_logged_and_skipped(self) -> None:
        """ImageUrlPart in message list is skipped and warning is logged."""
        client = self._make_client()
        messages = [
            ChatMessage(
                role=Role.USER,
                content=[
                    TextPart(text="describe this"),
                    ImageUrlPart(url="https://example.com/img.jpg"),
                ],
            )
        ]

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            mock_logger = MagicMock()
            with patch("quadkit.ai.llm.clients.cohere.logger", mock_logger):
                _http_client, payload, _model = client._build_payload(
                    messages, stream=False, kwargs={}
                )

                # The text part should be extracted, image part should not break anything
                assert payload["message"] == "describe this"
                # Assert logger.warning was called for the image part
                mock_logger.warning.assert_called_once()

    def test_multimodal_content_union_type_handled(self) -> None:
        """MessageContent union type (str | list[ContentPart]) is properly handled."""
        client = self._make_client()

        # Test string content
        messages_str = [ChatMessage(role=Role.USER, content="plain text")]

        # Test list content
        messages_list = [
            ChatMessage(
                role=Role.USER,
                content=[TextPart(text="from list")],
            )
        ]

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            with patch(
                "quadkit.ai.llm.clients._cohere_mappers.serialize_text_only",
                return_value="plain text",
            ) as mock_serialize_str:
                # Both should work without errors
                _http_client, payload_str, _ = client._build_payload(
                    messages_str, stream=False, kwargs={}
                )
                assert payload_str["message"] == "plain text"
                mock_serialize_str.assert_called_once()

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            with patch(
                "quadkit.ai.llm.clients._cohere_mappers.serialize_text_only",
                return_value="from list",
            ) as mock_serialize_list:
                _http_client, payload_list, _ = client._build_payload(
                    messages_list, stream=False, kwargs={}
                )
                assert payload_list["message"] == "from list"
                mock_serialize_list.assert_called_once()

    def test_base64_image_part_logged_and_skipped(self) -> None:
        """ImageBase64Part in message list is skipped and warning is logged."""
        client = self._make_client()
        messages = [
            ChatMessage(
                role=Role.USER,
                content=[
                    TextPart(text="caption"),
                    ImageBase64Part(data="abc123", media_type="image/png"),
                ],
            )
        ]

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            mock_logger = MagicMock()
            with patch("quadkit.ai.llm.clients.cohere.logger", mock_logger):
                _http_client, payload, _ = client._build_payload(
                    messages, stream=False, kwargs={}
                )

                # The text part should be extracted, image part should not break anything
                assert payload["message"] == "caption"
                # Assert logger.warning was called for the image part
                mock_logger.warning.assert_called_once()
