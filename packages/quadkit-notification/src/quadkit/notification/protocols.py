"""quadkit-notification protocol re-exports."""

from __future__ import annotations

from quadkit.contracts.mailer.protocols import MailerProtocol
from quadkit.contracts.notification.inbox import InboxStoreProtocol
from quadkit.contracts.notification.protocols import (
    DeliveryChannelProtocol,
    DeliveryDispatcherProtocol,
    PushChannelProtocol,
    SMSChannelProtocol,
)

__all__ = [
    "DeliveryChannelProtocol",
    "DeliveryDispatcherProtocol",
    "InboxStoreProtocol",
    "MailerProtocol",
    "PushChannelProtocol",
    "SMSChannelProtocol",
]
