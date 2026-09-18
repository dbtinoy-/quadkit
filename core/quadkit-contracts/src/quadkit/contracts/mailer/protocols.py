# quadkit-contracts/src/quadkit/contracts/mailer/protocols.py
"""MailerProtocol — structural contract for email backends."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from quadkit.contracts.core.health import HealthCheckResult
    from quadkit.contracts.core.result import Result
    from quadkit.contracts.mailer.errors import MailerError
    from quadkit.contracts.mailer.types import EmailMessage, MessageDeliveryReceipt


@runtime_checkable
class MailerProtocol(Protocol):
    """Structural protocol for email delivery backends.

    All mailer backends (SMTP, SendGrid, SES, etc.) must satisfy this
    protocol for Named DI resolution.  ``send()`` accepts a fully-formed
    :class:`~quadkit.contracts.mailer.types.EmailMessage` and
    returns ``Ok(receipt)`` on success or ``Err(MailerError)`` for expected
    delivery failures.  Infrastructure failures (authentication, network
    timeout) must be raised as exceptions, not wrapped in ``Err``.
    """

    async def send(
        self, message: EmailMessage
    ) -> Result[MessageDeliveryReceipt, MailerError]:
        """Send an email message.

        Args:
            message: The email to deliver.

        Returns:
            ``Ok(MessageDeliveryReceipt)`` on acceptance by the backend.
            ``Err(MailerError)`` for expected delivery failures.
        """
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check backend connectivity.

        Args:
            timeout: Maximum seconds to wait for a response.

        Returns:
            :class:`~quadkit.contracts.core.HealthCheckResult` with status details.
        """
        ...


__all__ = ["MailerProtocol"]
