"""Domain events for quadkit-notification — root namespace.

Emitted when top-level notification operations complete. Consumed by
audit, analytics, and delivery monitoring systems.
"""

from __future__ import annotations

from dataclasses import dataclass

from quadkit.contracts.domain.events import DomainEvent

__all__ = [
    "EmailBouncedEvent",
    "EmailSentEvent",
    "InboxMessageCreatedEvent",
    "InboxMessageReadEvent",
    "NotificationFailedEvent",
    "NotificationSentEvent",
]


# === Existing Notification Events ===


@dataclass(frozen=True, init=False)
class NotificationSentEvent(DomainEvent):
    """Emitted when a notification is successfully dispatched.

    Consumed by: audit, analytics, delivery tracking.
    """

    notification_id: str
    channel: str
    recipient_id: str


@dataclass(frozen=True, init=False)
class NotificationFailedEvent(DomainEvent):
    """Emitted when a notification dispatch fails permanently.

    Consumed by: audit, alerting, retry management.
    """

    notification_id: str
    channel: str
    reason: str


# === Mail Events (merged from mail/events.py) ===


@dataclass(frozen=True, init=False)
class EmailSentEvent(DomainEvent):
    """Emitted when an email is successfully dispatched to the provider.

    Consumed by: audit, analytics, delivery tracking.
    """

    message_id: str
    recipient: str
    template: str | None


@dataclass(frozen=True, init=False)
class EmailBouncedEvent(DomainEvent):
    """Emitted when an email bounces (hard or soft).

    Consumed by: bounce management, list hygiene, audit.
    """

    message_id: str
    recipient: str
    bounce_type: str


# === Inbox Events (merged from inbox/events.py) ===


@dataclass(frozen=True, init=False)
class InboxMessageCreatedEvent(DomainEvent):
    """Emitted when a new message is added to a user's inbox.

    Consumed by: audit, analytics, delivery tracking.
    """

    message_id: str
    user_id: str


@dataclass(frozen=True, init=False)
class InboxMessageReadEvent(DomainEvent):
    """Emitted when a user reads an inbox message.

    Consumed by: audit, analytics, engagement tracking.
    """

    message_id: str
    user_id: str
