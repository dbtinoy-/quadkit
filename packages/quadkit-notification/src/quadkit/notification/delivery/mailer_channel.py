"""Adapter from the durable outbox envelope to ``MailerProtocol``."""

from __future__ import annotations

from quadkit.contracts.mailer import (
    EmailMessage,
    MailerProtocol,
    MessageDeliveryReceipt,
)
from quadkit.contracts.notification.errors import NotificationError
from quadkit.contracts.notification.types import DeliveryMessage
from quadkit.result import Err, Ok, Result


class MailerDeliveryChannel:
    """Deliver queued email messages through the provider's raw mail backend."""

    channel = "email"

    def __init__(self, backend: MailerProtocol) -> None:
        """Initialize with the raw backend supplied by ``MailerDeliveryRuntime``."""
        self._backend = backend

    async def send(
        self, message: DeliveryMessage
    ) -> Result[MessageDeliveryReceipt, NotificationError]:
        """Map a queued envelope to ``EmailMessage`` and send it.

        Args:
            message: Channel-neutral outbox payload.

        Returns:
            The backend receipt on success or a notification-domain error.

        Raises:
            Exception: Infrastructure failures from the mail backend propagate
                to the framework worker, which schedules the retry.
        """
        options = message.metadata.get("email", {})
        if not isinstance(options, dict):
            options = {}
        recipient_list = [
            recipient.strip()
            for recipient in message.recipient.split(",")
            if recipient.strip()
        ]
        if not recipient_list or not message.subject:
            return Err(
                NotificationError(
                    "Email delivery requires a recipient and subject",
                    channel="email",
                    backend="mailer",
                )
            )

        email = EmailMessage(
            to=recipient_list,
            subject=message.subject,
            body=message.body,
            html_body=_optional_string(options.get("html_body")),
            from_email=_optional_string(options.get("from_email")),
            from_name=_optional_string(options.get("from_name")),
            reply_to=_optional_string(options.get("reply_to")),
            cc=_string_list(options.get("cc")),
            bcc=_string_list(options.get("bcc")),
            headers=_string_mapping(options.get("headers")),
        )
        result = await self._backend.send(email)
        if result.is_ok():
            return Ok(result.unwrap())
        error = result.unwrap_err()
        return Err(
            NotificationError(
                str(error),
                channel="email",
                backend="mailer",
                details={"mailer_error": str(error)},
            )
        )


def _optional_string(value: object) -> str | None:
    """Return a string option without accepting arbitrary structured values."""
    return value if isinstance(value, str) and value else None


def _string_list(value: object) -> list[str]:
    """Normalize a persisted sequence of strings."""
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _string_mapping(value: object) -> dict[str, str]:
    """Normalize persisted header keys and values."""
    if not isinstance(value, dict):
        return {}
    return {
        key: item
        for key, item in value.items()
        if isinstance(key, str) and isinstance(item, str)
    }


__all__ = ["MailerDeliveryChannel"]
