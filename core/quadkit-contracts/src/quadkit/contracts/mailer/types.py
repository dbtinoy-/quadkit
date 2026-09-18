# quadkit-contracts/src/quadkit/contracts/mailer/types.py
"""Mailer value types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import re
from typing import TYPE_CHECKING

from quadkit.contracts.lib.time import utcnow as _utcnow

if TYPE_CHECKING:
    from datetime import datetime

_HEADER_NAME_RE = re.compile(r"[!-9;-~]+")
"""RFC 5322 field-name token: printable ASCII excluding space and colon."""


def _reject_crlf(value: str | None, field: str) -> None:
    """Reject CR/LF in a field that will be serialized into a MIME header.

    Args:
        value: Field value to check; ``None`` passes.
        field: Human-readable field path for the error message.

    Raises:
        ValueError: If the value contains a CR or LF character.
    """
    if value is not None and ("\r" in value or "\n" in value):
        raise ValueError(f"{field} must not contain CR or LF characters")


@dataclass(frozen=True)
class EmailMessage:
    """A cross-channel email message value object.

    Passed to :class:`~quadkit.contracts.mailer.protocols.MailerProtocol`.
    All fields except *to* and *subject* are optional to keep simple use
    cases concise.

    Attributes:
        to: List of recipient email addresses.
        subject: Email subject line.
        body: Plain-text message body.
        html_body: HTML message body; falls back to *body* when absent.
        from_email: Sender address; implementations should supply a
            safe default when ``None``.
        from_name: Human-readable sender name.
        reply_to: Optional reply-to address.
        cc: Carbon-copy recipients.
        bcc: Blind carbon-copy recipients.
        headers: Additional MIME headers.
    """

    to: list[str]
    subject: str
    body: str = ""
    html_body: str | None = None
    from_email: str | None = None
    from_name: str | None = None
    reply_to: str | None = None
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Reject CR/LF in header-bound fields to prevent SMTP header injection.

        Only fields that are serialized into MIME headers are constrained;
        ``body`` and ``html_body`` are message content and may contain
        newlines. Raise (fail closed) rather than silently stripping, so a
        caller never believes an altered message was delivered as written.

        Raises:
            ValueError: If any header-bound field contains CR/LF or a
                header name is not a valid RFC 5322 field-name token.
        """
        _reject_crlf(self.subject, "EmailMessage.subject")
        _reject_crlf(self.from_email, "EmailMessage.from_email")
        _reject_crlf(self.from_name, "EmailMessage.from_name")
        _reject_crlf(self.reply_to, "EmailMessage.reply_to")
        for recipient_field, recipients in (
            ("to", self.to),
            ("cc", self.cc),
            ("bcc", self.bcc),
        ):
            for recipient in recipients:
                _reject_crlf(recipient, f"EmailMessage.{recipient_field}")
        for name, value in self.headers.items():
            if not _HEADER_NAME_RE.fullmatch(name):
                raise ValueError(
                    f"EmailMessage.headers contains invalid header name: {name!r}"
                )
            _reject_crlf(value, f"EmailMessage.headers[{name!r}]")


@dataclass(frozen=True)
class MessageDeliveryReceipt:
    """Confirmation that a message was accepted by the delivery backend.

    This is the success value returned by all messaging send operations.
    It does NOT guarantee delivery to the end recipient; it only confirms
    that the backend accepted the request.

    Attributes:
        message_id: Unique identifier for the message, assigned by the
            framework (or the backend when ``provider_reference`` differs).
        backend: Name of the backend that handled the send.
        channel: Delivery channel: ``"email"``, ``"sms"``, or ``"push"``.
        sent_at: UTC timestamp when the backend accepted the message.
        provider_reference: Opaque reference returned by the external
            provider. ``None`` when the backend does not return a reference.
    """

    message_id: str
    backend: str
    channel: str
    sent_at: datetime = field(default_factory=_utcnow)
    provider_reference: str | None = None


class MessagePriority(StrEnum):
    """Message delivery priority."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MessageStatus(StrEnum):
    """Outbound message status."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DeliveryState(StrEnum):
    """Downstream delivery state reported by provider."""

    QUEUED = "queued"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    REJECTED = "rejected"
    DEFERRED = "deferred"


@dataclass(frozen=True)
class MessageAddress:
    """An email address with an optional display name.

    Attributes:
        email: RFC-5321 email address.
        name: Human-readable display name; omitted when ``None``.
    """

    email: str
    name: str | None = None

    def __str__(self) -> str:
        if self.name:
            return f"{self.name} <{self.email}>"
        return self.email


@dataclass(frozen=True)
class Attachment:
    """An email attachment.

    Attributes:
        filename: Suggested filename shown to the recipient.
        content: Raw bytes of the attachment.
        content_type: MIME type; defaults to ``application/octet-stream``.
        content_id: Optional CID for inline embedding (e.g. ``cid:logo``).
    """

    filename: str
    content: bytes
    content_type: str = "application/octet-stream"
    content_id: str | None = None


__all__ = [
    "Attachment",
    "DeliveryState",
    "EmailMessage",
    "MessageAddress",
    "MessageDeliveryReceipt",
    "MessagePriority",
    "MessageStatus",
]
