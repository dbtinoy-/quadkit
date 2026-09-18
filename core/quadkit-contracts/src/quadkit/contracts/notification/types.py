# quadkit-contracts/src/quadkit/contracts/notification/types.py
"""Notification value types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SMSMessage:
    """An SMS notification message.

    Attributes:
        to: List of E.164-format recipient phone numbers.
        body: SMS body text (max 1600 chars; providers split if needed).
        from_number: Sender ID or phone number; backend default when ``None``.
        metadata: Opaque provider-specific metadata.
    """

    to: list[str]
    body: str
    from_number: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PushMessage:
    """A push notification message.

    Attributes:
        to: List of device tokens (FCM registration IDs, APNS tokens, etc.).
        title: Notification title.
        body: Notification body text.
        data: Custom key-value payload delivered to the app.
        badge: iOS badge count; ``None`` leaves badge unchanged.
        sound: Notification sound name; ``None`` uses OS default.
        image: URL of a large notification image.
        ttl: Time-to-live in seconds; ``None`` uses provider default.
    """

    to: list[str]
    title: str
    body: str
    data: dict[str, Any] = field(default_factory=dict)
    badge: int | None = None
    sound: str | None = None
    image: str | None = None
    ttl: int | None = None


__all__ = ["PushMessage", "SMSMessage"]
