"""Tests for notification types."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from quadkit.contracts.notification.types import PushMessage, SMSMessage


class TestSMSMessage:
    """Tests for SMSMessage."""

    def test_creation(self) -> None:
        """Test creating an SMSMessage."""
        msg = SMSMessage(to=["+1234567890"], body="Hello!")
        assert msg.to == ["+1234567890"]
        assert msg.body == "Hello!"
        assert msg.from_number is None

    def test_default_values(self) -> None:
        """Test SMSMessage has correct defaults."""
        msg = SMSMessage(to=["+1234567890"], body="Hello!")
        assert msg.metadata == {}
        assert msg.from_number is None

    def test_custom_values(self) -> None:
        """Test SMSMessage with custom values."""
        msg = SMSMessage(
            to=["+1234567890", "+0987654321"],
            body="Test message",
            from_number="+1111111111",
            metadata={"priority": "high"},
        )
        assert msg.to == ["+1234567890", "+0987654321"]
        assert msg.from_number == "+1111111111"
        assert msg.metadata == {"priority": "high"}

    def test_frozen_dataclass(self) -> None:
        """Test SMSMessage is frozen (immutable)."""
        msg = SMSMessage(to=["+1234567890"], body="Hello!")
        with pytest.raises(FrozenInstanceError):
            msg.body = "New message"


class TestPushMessage:
    """Tests for PushMessage."""

    def test_creation(self) -> None:
        """Test creating a PushMessage."""
        msg = PushMessage(
            to=["token123"],
            title="Alert",
            body="You have a new message",
        )
        assert msg.to == ["token123"]
        assert msg.title == "Alert"
        assert msg.body == "You have a new message"

    def test_default_values(self) -> None:
        """Test PushMessage has correct defaults."""
        msg = PushMessage(to=["token123"], title="Alert", body="Message")
        assert msg.data == {}
        assert msg.badge is None
        assert msg.sound is None
        assert msg.image is None
        assert msg.ttl is None

    def test_custom_values(self) -> None:
        """Test PushMessage with custom values."""
        msg = PushMessage(
            to=["token1", "token2"],
            title="Title",
            body="Body",
            data={"action": "open"},
            badge=5,
            sound="custom.mp3",
            image="https://example.com/image.png",
            ttl=3600,
        )
        assert msg.data == {"action": "open"}
        assert msg.badge == 5
        assert msg.sound == "custom.mp3"
        assert msg.image == "https://example.com/image.png"
        assert msg.ttl == 3600

    def test_multiple_tokens(self) -> None:
        """Test PushMessage can have multiple device tokens."""
        msg = PushMessage(
            to=["token1", "token2", "token3"],
            title="Broadcast",
            body="Message to all devices",
        )
        assert len(msg.to) == 3

    def test_frozen_dataclass(self) -> None:
        """Test PushMessage is frozen (immutable)."""
        msg = PushMessage(to=["token123"], title="Alert", body="Message")
        with pytest.raises(FrozenInstanceError):
            msg.title = "New Title"


class TestNotificationIntegration:
    """Integration tests for notification types."""

    @pytest.mark.asyncio
    async def test_can_use_in_async_context(self) -> None:
        """Test notification types work in async functions."""

        async def send_sms(msg: SMSMessage) -> str:
            return f"Sent to {len(msg.to)} recipients: {msg.body}"

        msg = SMSMessage(to=["+1234567890"], body="Test")
        result = await send_sms(msg)
        assert result == "Sent to 1 recipients: Test"

    def test_can_convert_to_dict(self) -> None:
        """Test notification types can be converted to dict."""
        from dataclasses import asdict

        sms = SMSMessage(to=["+1234567890"], body="Hello")
        push = PushMessage(
            to=["token123"],
            title="Alert",
            body="Message",
            data={"key": "value"},
        )

        sms_dict = asdict(sms)
        push_dict = asdict(push)

        assert sms_dict["to"] == ["+1234567890"]
        assert sms_dict["body"] == "Hello"
        assert push_dict["title"] == "Alert"
        assert push_dict["data"] == {"key": "value"}
