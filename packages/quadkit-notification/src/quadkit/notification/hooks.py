"""Root hook payload surface for quadkit-notification.

Defines canonical payload dataclasses for notification delivery hook points.
Actual hook registration and invocation use the framework's string-keyed
``HookRegistryProtocol`` action/filter APIs.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "EmailDispatchedHook",
    "EmailRenderedHook",
    "InboxMessageCreatedHook",
    "InboxMessageReadHook",
    "NotificationFailedHook",
    "NotificationSentHook",
]


# === Existing Notification Hooks ===


@dataclass(frozen=True, kw_only=True)
class NotificationSentHook:
    """Payload fired when a notification is successfully dispatched.

    Attributes:
        channel: Delivery channel used (e.g. ``"email"``, ``"sms"``, ``"push"``).
        recipient_id: Identifier of the notification recipient.
    """

    channel: str
    recipient_id: str


@dataclass(frozen=True, kw_only=True)
class NotificationFailedHook:
    """Payload fired when a notification dispatch attempt fails.

    Attributes:
        channel: Delivery channel that failed.
        recipient_id: Identifier of the intended recipient.
        reason: Short description of the failure.
    """

    channel: str
    recipient_id: str
    reason: str


# === Mail Hooks (merged from mail/hooks.py) ===


@dataclass(frozen=True)
class EmailDispatchedHook:
    """Payload fired when an email is dispatched to the sending provider.

    Attributes:
        recipient: Email address of the recipient.
        message_id: Provider-assigned message identifier.
        backend: Name of the sending backend (e.g., "sendgrid", "ses").
    """

    recipient: str
    message_id: str
    backend: str


@dataclass(frozen=True)
class EmailRenderedHook:
    """Payload fired when an email template is rendered.

    Attributes:
        template_name: Name of the template used.
        recipient: Target recipient email address.
    """

    template_name: str
    recipient: str


# === Inbox Hooks (merged from inbox/hooks.py) ===


@dataclass(frozen=True)
class InboxMessageCreatedHook:
    """Payload fired when a new message is added to a user's inbox.

    Attributes:
        message_id: Unique identifier of the inbox message.
        user_id: Identifier of the recipient user.
    """

    message_id: str
    user_id: str


@dataclass(frozen=True)
class InboxMessageReadHook:
    """Payload fired when a user opens an inbox message.

    Attributes:
        message_id: Unique identifier of the inbox message.
        user_id: Identifier of the user who read the message.
    """

    message_id: str
    user_id: str
