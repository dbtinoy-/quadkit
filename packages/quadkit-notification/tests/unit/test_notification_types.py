"""Unit tests for notification types."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from quadkit.notification.types import (
    Attachment,
    DeliveryState,
    EmailMessage,
    InboxMessageStatus,
    InboxPageResult,
    InboxQuery,
    InboxStats,
    MessageAddress,
    MessageDeliveryReceipt,
    MessagePriority,
    MessageStatus,
    PushMessage,
    SMSMessage,
)


class TestInboxMessageStatus:
    """Tests for InboxMessageStatus enum."""

    def test_enum_values(self) -> None:
        assert InboxMessageStatus.ARCHIVED.value == "archived"
        assert InboxMessageStatus.READ.value == "read"
        assert InboxMessageStatus.UNREAD.value == "unread"

    def test_enum_members(self) -> None:
        members = list(InboxMessageStatus)
        assert len(members) == 3
        assert InboxMessageStatus.ARCHIVED in members
        assert InboxMessageStatus.READ in members
        assert InboxMessageStatus.UNREAD in members

    def test_enum_is_string_enum(self) -> None:
        assert isinstance(InboxMessageStatus.READ, str)
        assert InboxMessageStatus.READ == "read"


class TestInboxQuery:
    """Tests for InboxQuery dataclass."""

    def test_default_values(self) -> None:
        query = InboxQuery(user_id="user-123")
        assert query.user_id == "user-123"
        assert query.page == 1
        assert query.page_size == 20
        assert query.unread_only is False

    def test_custom_values(self) -> None:
        query = InboxQuery(user_id="user-456", page=2, page_size=50, unread_only=True)
        assert query.user_id == "user-456"
        assert query.page == 2
        assert query.page_size == 50
        assert query.unread_only is True

    def test_is_frozen(self) -> None:
        query = InboxQuery(user_id="user-123")
        with pytest.raises(AttributeError):
            query.page = 5

    def test_is_kw_only(self) -> None:
        with pytest.raises(TypeError):
            InboxQuery("user-123")


class TestInboxPageResult:
    """Tests for InboxPageResult dataclass."""

    def test_fields(self) -> None:
        result = InboxPageResult(
            items=[],
            total=100,
            page=1,
            page_size=20,
            has_next=True,
        )
        assert result.items == []
        assert result.total == 100
        assert result.page == 1
        assert result.page_size == 20
        assert result.has_next is True

    def test_is_frozen(self) -> None:
        result = InboxPageResult(items=[], total=0, page=1, page_size=20, has_next=False)
        with pytest.raises(AttributeError):
            result.page = 2


class TestInboxStats:
    """Tests for InboxStats dataclass."""

    def test_fields(self) -> None:
        stats = InboxStats(user_id="user-123", total_count=50, unread_count=10)
        assert stats.user_id == "user-123"
        assert stats.total_count == 50
        assert stats.unread_count == 10

    def test_is_frozen(self) -> None:
        stats = InboxStats(user_id="user-123", total_count=50, unread_count=10)
        with pytest.raises(AttributeError):
            stats.total_count = 100


class TestReExports:
    """Tests for re-exported types from contracts."""

    def test_attachment_import(self) -> None:
        assert Attachment is not None

    def test_delivery_state_import(self) -> None:
        assert DeliveryState is not None

    def test_email_message_import(self) -> None:
        assert EmailMessage is not None

    def test_message_address_import(self) -> None:
        assert MessageAddress is not None

    def test_message_delivery_receipt_import(self) -> None:
        assert MessageDeliveryReceipt is not None

    def test_message_priority_import(self) -> None:
        assert MessagePriority is not None

    def test_message_status_import(self) -> None:
        assert MessageStatus is not None

    def test_push_message_import(self) -> None:
        assert PushMessage is not None

    def test_sms_message_import(self) -> None:
        assert SMSMessage is not None