# quadkit-contracts/src/quadkit/contracts/mailer/__init__.py
"""Mailer protocols, types, and errors."""

from __future__ import annotations

from quadkit.contracts.mailer.errors import MailerError
from quadkit.contracts.mailer.protocols import MailerProtocol
from quadkit.contracts.mailer.types import (
    Attachment,
    DeliveryState,
    EmailMessage,
    MessageAddress,
    MessageDeliveryReceipt,
    MessagePriority,
    MessageStatus,
)

__all__ = [
    "Attachment",
    "DeliveryState",
    "EmailMessage",
    "MailerError",
    "MailerProtocol",
    "MessageAddress",
    "MessageDeliveryReceipt",
    "MessagePriority",
    "MessageStatus",
]
