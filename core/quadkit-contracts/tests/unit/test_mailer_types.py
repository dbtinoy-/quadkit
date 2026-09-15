"""Tests for mailer types."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from quadkit.contracts.mailer.types import (
    Attachment,
    DeliveryState,
    EmailMessage,
    MessageAddress,
    MessageDeliveryReceipt,
    MessagePriority,
    MessageStatus,
)


class TestEmailMessage:
    """Tests for EmailMessage."""

    def test_creation(self) -> None:
        """Test creating an EmailMessage."""
        msg = EmailMessage(to=["test@example.com"], subject="Hello")
        assert msg.to == ["test@example.com"]
        assert msg.subject == "Hello"

    def test_default_values(self) -> None:
        """Test EmailMessage has correct defaults."""
        msg = EmailMessage(to=["test@example.com"], subject="Test")
        assert msg.body == ""
        assert msg.html_body is None
        assert msg.from_email is None
        assert msg.from_name is None
        assert msg.reply_to is None
        assert msg.cc == []
        assert msg.bcc == []
        assert msg.headers == {}

    def test_custom_values(self) -> None:
        """Test EmailMessage with custom values."""
        msg = EmailMessage(
            to=["recipient@example.com"],
            subject="Test Subject",
            body="Plain text body",
            html_body="<p>HTML body</p>",
            from_email="sender@example.com",
            from_name="Sender Name",
            reply_to="reply@example.com",
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
            headers={"X-Custom": "value"},
        )
        assert msg.body == "Plain text body"
        assert msg.html_body == "<p>HTML body</p>"
        assert msg.from_email == "sender@example.com"
        assert msg.cc == ["cc@example.com"]
        assert msg.headers == {"X-Custom": "value"}

    def test_multiple_recipients(self) -> None:
        """Test EmailMessage with multiple recipients."""
        msg = EmailMessage(
            to=["a@example.com", "b@example.com"],
            subject="Test",
            cc=["c@example.com"],
            bcc=["d@example.com"],
        )
        assert len(msg.to) == 2
        assert len(msg.cc) == 1
        assert len(msg.bcc) == 1


class TestMessageDeliveryReceipt:
    """Tests for MessageDeliveryReceipt."""

    def test_creation(self) -> None:
        """Test creating a MessageDeliveryReceipt."""
        receipt = MessageDeliveryReceipt(
            message_id="msg-123",
            backend="smtp",
            channel="email",
        )
        assert receipt.message_id == "msg-123"
        assert receipt.backend == "smtp"
        assert receipt.channel == "email"

    def test_default_values(self) -> None:
        """Test MessageDeliveryReceipt has correct defaults."""
        receipt = MessageDeliveryReceipt(
            message_id="msg-123",
            backend="smtp",
            channel="email",
        )
        assert receipt.sent_at is not None
        assert receipt.provider_reference is None

    def test_custom_values(self) -> None:
        """Test MessageDeliveryReceipt with custom values."""
        now = datetime(2024, 1, 1, tzinfo=UTC)
        receipt = MessageDeliveryReceipt(
            message_id="msg-123",
            backend="ses",
            channel="email",
            sent_at=now,
            provider_reference="ref-456",
        )
        assert receipt.sent_at == now
        assert receipt.provider_reference == "ref-456"

    def test_frozen_dataclass(self) -> None:
        """Test MessageDeliveryReceipt is frozen."""
        receipt = MessageDeliveryReceipt(
            message_id="msg-123",
            backend="smtp",
            channel="email",
        )
        with pytest.raises(FrozenInstanceError):
            receipt.message_id = "new-id"


class TestMessageAddress:
    """Tests for MessageAddress."""

    def test_creation(self) -> None:
        """Test creating a MessageAddress."""
        addr = MessageAddress(email="test@example.com")
        assert addr.email == "test@example.com"
        assert addr.name is None

    def test_with_name(self) -> None:
        """Test MessageAddress with display name."""
        addr = MessageAddress(email="test@example.com", name="Test User")
        assert addr.name == "Test User"

    def test_str_without_name(self) -> None:
        """Test string representation without name."""
        addr = MessageAddress(email="test@example.com")
        assert str(addr) == "test@example.com"

    def test_str_with_name(self) -> None:
        """Test string representation with name."""
        addr = MessageAddress(email="test@example.com", name="Test User")
        assert str(addr) == "Test User <test@example.com>"

    def test_frozen_dataclass(self) -> None:
        """Test MessageAddress is frozen."""
        addr = MessageAddress(email="test@example.com")
        with pytest.raises(FrozenInstanceError):
            addr.email = "new@example.com"


class TestAttachment:
    """Tests for Attachment."""

    def test_creation(self) -> None:
        """Test creating an Attachment."""
        att = Attachment(filename="file.txt", content=b"content")
        assert att.filename == "file.txt"
        assert att.content == b"content"

    def test_default_content_type(self) -> None:
        """Test Attachment has correct default content type."""
        att = Attachment(filename="file.txt", content=b"content")
        assert att.content_type == "application/octet-stream"

    def test_custom_values(self) -> None:
        """Test Attachment with custom values."""
        att = Attachment(
            filename="image.png",
            content=b"png-data",
            content_type="image/png",
            content_id="logo",
        )
        assert att.content_type == "image/png"
        assert att.content_id == "logo"

    def test_frozen_dataclass(self) -> None:
        """Test Attachment is frozen."""
        att = Attachment(filename="file.txt", content=b"content")
        with pytest.raises(FrozenInstanceError):
            att.filename = "new.txt"


class TestEnums:
    """Tests for mailer enums."""

    def test_message_priority_values(self) -> None:
        """Test MessagePriority enum values."""
        assert MessagePriority.LOW.value == "low"
        assert MessagePriority.NORMAL.value == "normal"
        assert MessagePriority.HIGH.value == "high"
        assert MessagePriority.URGENT.value == "urgent"

    def test_message_status_values(self) -> None:
        """Test MessageStatus enum values."""
        assert MessageStatus.PENDING.value == "pending"
        assert MessageStatus.SENT.value == "sent"
        assert MessageStatus.FAILED.value == "failed"
        assert MessageStatus.CANCELLED.value == "cancelled"

    def test_delivery_state_values(self) -> None:
        """Test DeliveryState enum values."""
        assert DeliveryState.QUEUED.value == "queued"
        assert DeliveryState.DELIVERED.value == "delivered"
        assert DeliveryState.BOUNCED.value == "bounced"
        assert DeliveryState.REJECTED.value == "rejected"
        assert DeliveryState.DEFERRED.value == "deferred"

    def test_enums_are_str_enum(self) -> None:
        """Test all enums are StrEnum."""
        assert isinstance(MessagePriority.LOW.value, str)
        assert isinstance(MessageStatus.PENDING.value, str)
        assert isinstance(DeliveryState.QUEUED.value, str)


class TestMailerIntegration:
    """Integration tests for mailer types."""

    def test_can_build_complete_email(self) -> None:
        """Test building a complete email with all options."""
        msg = EmailMessage(
            to=["recipient@example.com"],
            subject="Test Email",
            body="Plain text version",
            html_body="<p>HTML version</p>",
            from_email="sender@example.com",
            from_name="Sender",
            cc=["cc@example.com"],
            headers={"X-Priority": "1"},
        )
        assert msg.to == ["recipient@example.com"]
        assert msg.cc == ["cc@example.com"]

    def test_can_use_address_in_email(self) -> None:
        """Test using MessageAddress in EmailMessage."""
        addr = MessageAddress(email="test@example.com", name="Test")
        msg = EmailMessage(
            to=[addr.email],
            subject="Test",
            from_email=addr.email,
            from_name=addr.name,
        )
        assert msg.to[0] == "test@example.com"
        assert msg.from_name == "Test"
