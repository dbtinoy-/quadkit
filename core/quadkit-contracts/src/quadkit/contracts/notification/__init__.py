# quadkit-contracts/src/quadkit/contracts/notification/__init__.py
"""Notification protocols, types, and errors."""

from __future__ import annotations

from quadkit.contracts.notification.delivery import (
    DeliveryStatus,
    DeliveryStoreProtocol,
)
from quadkit.contracts.notification.errors import NotificationError
from quadkit.contracts.notification.inbox import InboxMessage, InboxStoreProtocol
from quadkit.contracts.notification.protocols import (
    PushChannelProtocol,
    SMSChannelProtocol,
)
from quadkit.contracts.notification.types import PushMessage, SMSMessage
from quadkit.contracts.notification.web_push import WebPushKeys, WebPushSubscription

__all__ = [
    "DeliveryStatus",
    "DeliveryStoreProtocol",
    "InboxMessage",
    "InboxStoreProtocol",
    "NotificationError",
    "PushChannelProtocol",
    "PushMessage",
    "SMSChannelProtocol",
    "SMSMessage",
    "WebPushKeys",
    "WebPushSubscription",
]
