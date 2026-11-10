"""Test that Gemini/Vertex AI client serializes MessageContent correctly."""

from __future__ import annotations

from typing import Any, cast

from quadkit.ai.llm.clients.gemini_helpers import messages_to_gemini
from quadkit.ai.llm.types import ChatMessage
from quadkit.contracts.ai.llm import Role
from quadkit.contracts.ai.multimodal import (
    ImageBase64Part,
    ImageUrlPart,
    TextPart,
)


class TestGeminiMultimodal:
    """Test Gemini message serialization with multimodal content."""

    def test_string_content_becomes_text_part(self) -> None:
        """Plain string content converts to text part in Gemini format."""
        msg = ChatMessage(role=Role.USER, content="hello")
        result = messages_to_gemini(cast("list[dict[str, Any]]", [msg]))

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert result[0]["parts"] == [{"text": "hello"}]

    def test_assistant_role_becomes_model(self) -> None:
        """Assistant role converts to 'model' in Gemini format."""
        msg = ChatMessage(role=Role.ASSISTANT, content="hi")
        result = messages_to_gemini(cast("list[dict[str, Any]]", [msg]))

        assert len(result) == 1
        assert result[0]["role"] == "model"
        assert result[0]["parts"] == [{"text": "hi"}]

    def test_image_url_becomes_file_data(self) -> None:
        """ImageUrlPart converts to file_data with correct MIME type."""
        msg = ChatMessage(
            role=Role.USER,
            content=[ImageUrlPart(url="https://example.com/photo.jpg")],
        )
        result = messages_to_gemini(cast("list[dict[str, Any]]", [msg]))

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert len(result[0]["parts"]) == 1

        part = result[0]["parts"][0]
        assert "file_data" in part
        assert part["file_data"]["mime_type"] == "image/jpeg"
        assert part["file_data"]["file_uri"] == "https://example.com/photo.jpg"

    def test_base64_becomes_inline_data(self) -> None:
        """ImageBase64Part converts to inline_data with media type."""
        msg = ChatMessage(
            role=Role.USER,
            content=[ImageBase64Part(data="abc123", media_type="image/png")],
        )
        result = messages_to_gemini(cast("list[dict[str, Any]]", [msg]))

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert len(result[0]["parts"]) == 1

        part = result[0]["parts"][0]
        assert "inline_data" in part
        assert part["inline_data"]["mime_type"] == "image/png"
        assert part["inline_data"]["data"] == "abc123"

    def test_multimodal_content_mixed_parts(self) -> None:
        """Multimodal content with text and image parts serializes correctly."""
        msg = ChatMessage(
            role=Role.USER,
            content=[
                TextPart(text="describe this"),
                ImageUrlPart(url="https://example.com/img.png", detail="high"),
            ],
        )
        result = messages_to_gemini(cast("list[dict[str, Any]]", [msg]))

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert len(result[0]["parts"]) == 2

        # Check text part
        assert result[0]["parts"][0] == {"text": "describe this"}

        # Check image part
        assert result[0]["parts"][1] == {
            "file_data": {
                "mime_type": "image/png",
                "file_uri": "https://example.com/img.png",
            }
        }

    def test_image_url_with_query_string_preserved(self) -> None:
        """Image URL with query string is preserved in file_uri."""
        url = "https://example.com/image.jpg?width=100&height=200"
        msg = ChatMessage(
            role=Role.USER,
            content=[ImageUrlPart(url=url)],
        )
        result = messages_to_gemini(cast("list[dict[str, Any]]", [msg]))

        part = result[0]["parts"][0]
        assert part["file_data"]["file_uri"] == url

    def test_mime_type_detection_from_extension(self) -> None:
        """MIME type is correctly detected from file extension."""
        test_cases = [
            ("https://example.com/photo.jpg", "image/jpeg"),
            ("https://example.com/photo.png", "image/png"),
            ("https://example.com/photo.gif", "image/gif"),
            ("https://example.com/photo.webp", "image/webp"),
        ]

        for url, expected_mime in test_cases:
            msg = ChatMessage(
                role=Role.USER,
                content=[ImageUrlPart(url=url)],
            )
            result = messages_to_gemini(cast("list[dict[str, Any]]", [msg]))
            part = result[0]["parts"][0]
            assert part["file_data"]["mime_type"] == expected_mime, f"Failed for {url}"

    def test_multiple_messages_with_different_roles(self) -> None:
        """Multiple messages with different roles are serialized correctly."""
        messages = [
            ChatMessage(role=Role.USER, content="hello"),
            ChatMessage(role=Role.ASSISTANT, content="hi there"),
        ]
        result = messages_to_gemini(cast("list[dict[str, Any]]", messages))

        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[0]["parts"] == [{"text": "hello"}]
        assert result[1]["role"] == "model"
        assert result[1]["parts"] == [{"text": "hi there"}]

    def test_system_message_prepended_to_first_user_turn(self) -> None:
        """System message is prepended as text to the first user turn."""
        messages = [
            ChatMessage(role=Role.SYSTEM, content="You are helpful"),
            ChatMessage(role=Role.USER, content="hello"),
        ]
        result = messages_to_gemini(cast("list[dict[str, Any]]", messages))

        assert len(result) == 1
        assert result[0]["role"] == "user"
        assert len(result[0]["parts"]) == 2
        assert result[0]["parts"][0]["text"] == "You are helpful"
        assert result[0]["parts"][1]["text"] == "hello"

    def test_system_message_dropped_when_first_turn_is_assistant(self) -> None:
        """System message is silently dropped when the first non-system turn is an assistant role."""
        messages = [
            ChatMessage(role=Role.SYSTEM, content="You are helpful"),
            ChatMessage(role=Role.ASSISTANT, content="hello"),
            ChatMessage(role=Role.USER, content="world"),
        ]
        result = messages_to_gemini(cast("list[dict[str, Any]]", messages))

        assert len(result) == 2
        # First message (assistant) should not have system text
        assert result[0]["role"] == "model"
        assert result[0]["parts"] == [{"text": "hello"}]
        # Second message (user) should NOT have system text because it's not the first message
        assert result[1]["role"] == "user"
        assert result[1]["parts"] == [{"text": "world"}]

    def test_base64_image_data_with_media_type(self) -> None:
        """Base64 image data includes the correct media type."""
        msg = ChatMessage(
            role=Role.USER,
            content=[ImageBase64Part(data="base64data", media_type="image/jpeg")],
        )
        result = messages_to_gemini(cast("list[dict[str, Any]]", [msg]))

        part = result[0]["parts"][0]
        assert part == {
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": "base64data",
            }
        }
