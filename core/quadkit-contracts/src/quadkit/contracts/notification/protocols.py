# quadkit-contracts/src/quadkit/contracts/notification/protocols.py
"""Notification channel protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.core.health import HealthCheckResult
    from quadkit.contracts.core.result import Result
    from quadkit.contracts.mailer.types import MessageDeliveryReceipt
    from quadkit.contracts.notification.errors import NotificationError
    from quadkit.contracts.notification.types import PushMessage, SMSMessage


@runtime_checkable
class SMSChannelProtocol(Protocol):
    """Structural protocol for SMS backends (Twilio, Vonage, etc.).

    ``send()`` returns ``Ok(receipt)`` on acceptance or ``Err(NotificationError)``
    for expected failures.  Infrastructure failures must be raised as exceptions.
    """

    async def send(
        self, message: SMSMessage
    ) -> Result[MessageDeliveryReceipt, NotificationError]:
        """Send an SMS message.

        Args:
            message: The SMS to deliver.

        Returns:
            ``Ok(MessageDeliveryReceipt)`` or ``Err(NotificationError)``.
        """
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check SMS backend connectivity."""
        ...


@runtime_checkable
class PushChannelProtocol(Protocol):
    """Structural protocol for push notification backends (FCM, APNS, etc.).

    ``send()`` delivers to one or more device tokens.  ``send_batch()`` delivers
    to multiple tokens in one API call where the provider supports it.
    """

    async def send(
        self, message: PushMessage
    ) -> Result[MessageDeliveryReceipt, NotificationError]:
        """Send a push notification to one or more device tokens.

        Args:
            message: The push notification to deliver.

        Returns:
            ``Ok(MessageDeliveryReceipt)`` or ``Err(NotificationError)``.
        """
        ...

    async def send_batch(
        self, messages: list[PushMessage]
    ) -> list[Result[MessageDeliveryReceipt, NotificationError]]:
        """Send push notifications in bulk.

        Args:
            messages: List of push notifications to deliver.

        Returns:
            List of ``Result`` values, one per message, preserving order.
        """
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check push backend connectivity."""
        ...


__all__ = ["PushChannelProtocol", "SMSChannelProtocol"]
