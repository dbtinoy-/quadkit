"""Console mailer backend for development.

Logs every outgoing email to the backend console instead of delivering it
over the network.  Used automatically when no real backend is configured
(``MailerConfig.console_fallback``) or explicitly via ``driver: "console"``.

The verification/password-reset flows embed clickable links in the email
body, so in development the printed body is enough to complete the flow by
copying the link from the backend log.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.mailer import EmailMessage, MessageDeliveryReceipt
from quadkit.logging import get_logger
from quadkit.result import Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.mailer.errors import MailerError

logger = get_logger(__name__)


class ConsoleMailer:
    """MailerProtocol backend that prints emails to the application log.

    Implements :class:`~quadkit.contracts.mailer.protocols.MailerProtocol`.
    Never touches the network: the full message (subject, recipients, and
    body including any verification links) is emitted as a single structured
    log line so developers can see and use the content in local runs.

    Args:
        log_level: Structlog level name to emit at (``"info"``).  Useful to
            raise to ``"warning"`` in noisy logs.
    """

    def __init__(self, log_level: str = "info") -> None:
        """Initialise the console mailer.

        Args:
            log_level: Log level to emit messages at (default ``"info"``).
        """
        self.log_level = log_level

    async def send(
        self, message: EmailMessage
    ) -> Result[MessageDeliveryReceipt, MailerError]:
        """Log the email to the console and return a fake receipt.

        Args:
            message: The email to log.

        Returns:
            ``Ok(MessageDeliveryReceipt)`` — the message is always accepted.
        """
        log = getattr(logger, self.log_level, logger.info)
        log(
            "mailer.console_email",
            to=", ".join(message.to),
            subject=message.subject,
            from_email=message.from_email,
            body=message.body or "",
            html_body=message.html_body or "",
            # Named, not dumped: a developer needs to know the invoice
            # was attached, and a base64 PDF in the log helps nobody.
            attachments=[
                f"{attachment.filename} ({attachment.content_type}, "
                f"{len(attachment.content)} bytes)"
                for attachment in message.attachments
            ],
        )
        return Ok(
            MessageDeliveryReceipt(
                message_id=f"console-{uuid.uuid4().hex}",
                backend="console",
                channel="email",
                provider_reference="console",
            )
        )

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report the console backend as always healthy.

        Args:
            timeout: Ignored — no network I/O is performed.

        Returns:
            Healthy :class:`~quadkit.contracts.core.HealthCheckResult`.
        """
        return HealthCheckResult(
            component="mailer.console",
            status=HealthStatus.HEALTHY,
            message="Console mailer is available",
        )


__all__ = ["ConsoleMailer"]
