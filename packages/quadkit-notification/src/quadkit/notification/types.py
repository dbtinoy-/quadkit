"""quadkit-notification type re-exports."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from quadkit.contracts.mailer.types import (
    Attachment,
    DeliveryState,
    EmailMessage,
    MessageAddress,
    MessageDeliveryReceipt,
    MessagePriority,
    MessageStatus,
)
from quadkit.contracts.notification.types import (
    DeliveryMessage,
    PushMessage,
    SMSMessage,
)

__all__ = [
    "Attachment",
    "DeliveryMessage",
    "DeliveryState",
    "EmailMessage",
    "InboxMessageStatus",
    "InboxPageResult",
    "InboxQuery",
    "InboxStats",
    "MessageAddress",
    "MessageDeliveryReceipt",
    "MessagePriority",
    "MessageStatus",
    "PushMessage",
    "SMSMessage",
]


# === Inbox Types (merged from inbox/types.py) ===


class InboxMessageStatus(str, Enum):
    """Status of an inbox message."""

    ARCHIVED = "archived"
    READ = "read"
    UNREAD = "unread"


@dataclass(frozen=True, kw_only=True)
class InboxQuery:
    """Parameters for paginated inbox message queries.

    Attributes:
        user_id: Identifier of the user whose inbox to query.
        page: Page number (1-indexed).
        page_size: Number of results per page.
        unread_only: When True, return only unread messages.
    """

    user_id: str
    page: int = 1
    page_size: int = 20
    unread_only: bool = False


@dataclass(frozen=True, kw_only=True)
class InboxPageResult:
    """Paginated result of an inbox query.

    Attributes:
        items: List of inbox message objects for this page.
        total: Total number of matching messages.
        page: Current page number.
        page_size: Number of items per page.
        has_next: Whether there is a next page.
    """

    items: list[object]
    total: int
    page: int
    page_size: int
    has_next: bool


@dataclass(frozen=True, kw_only=True)
class InboxStats:
    """Aggregate statistics for a user's inbox.

    Attributes:
        user_id: Identifier of the user.
        total_count: Total number of messages in the inbox.
        unread_count: Number of unread messages.
    """

    user_id: str
    total_count: int
    unread_count: int
