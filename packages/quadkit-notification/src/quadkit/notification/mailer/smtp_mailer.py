"""SMTP mailer backend."""

from __future__ import annotations

import asyncio
from email import encoders
from email.errors import MessageError
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
import ssl
from typing import TYPE_CHECKING
import uuid

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.mailer import (
    EmailMessage,
    MessageDeliveryReceipt,
)
from quadkit.contracts.mailer.types import Attachment
from quadkit.logging import get_logger
from quadkit.notification.constants import DEFAULT_FROM_EMAIL
from quadkit.notification.exceptions import SMTPMailerError
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.mailer.errors import MailerError

logger = get_logger(__name__)


class SMTPMailer:
    """Email backend that sends via SMTP.

    Implements :class:`~quadkit.contracts.mailer.protocols.MailerProtocol`.
    SMTP operations are blocking; they are run in a thread pool via
    ``run_in_executor`` to avoid blocking the event loop.

    Args:
        host: SMTP server hostname.
        port: SMTP port (587 for TLS, 465 for SSL, 25 for plain).
        username: SMTP authentication username.
        password: SMTP authentication password.
        use_tls: Use STARTTLS after connection (port 587).
        use_ssl: Use SSL from the start (port 465).
        timeout: Connection timeout in seconds.
        from_email: Default sender address.
        from_name: Default sender display name.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 587,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
        use_ssl: bool = False,
        timeout: int = 30,
        from_email: str | None = None,
        from_name: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.timeout = timeout
        self.from_email = from_email or DEFAULT_FROM_EMAIL
        self.from_name = from_name

    def _build_mime(self, message: EmailMessage) -> MIMEMultipart:
        """Build MIME message from EmailMessage.

        With no attachments the message is a plain ``multipart/alternative``
        of the text and HTML bodies. With attachments it becomes a
        ``multipart/mixed`` whose first part is that alternative — the
        structure mail clients expect, and the one that keeps an HTML body
        rendering as a body rather than as a second download.
        """
        mime = (
            MIMEMultipart("mixed")
            if message.attachments
            else MIMEMultipart("alternative")
        )
        sender = (
            message.from_email if message.from_email is not None else self.from_email
        )
        display_name = (
            message.from_name if message.from_name is not None else self.from_name
        )
        mime["From"] = f"{display_name} <{sender}>" if display_name else sender
        mime["To"] = ", ".join(message.to)
        mime["Subject"] = message.subject
        if message.cc:
            mime["Cc"] = ", ".join(message.cc)
        for key, value in message.headers.items():
            mime[key] = value
        if message.attachments:
            alternative = MIMEMultipart("alternative")
            if message.body:
                alternative.attach(MIMEText(message.body, "plain", "utf-8"))
            if message.html_body:
                alternative.attach(MIMEText(message.html_body, "html", "utf-8"))
            mime.attach(alternative)
            for attachment in message.attachments:
                mime.attach(_build_part(attachment))
            return mime
        if message.body:
            mime.attach(MIMEText(message.body, "plain", "utf-8"))
        if message.html_body:
            mime.attach(MIMEText(message.html_body, "html", "utf-8"))
        return mime

    def _send_sync(self, mime: MIMEMultipart, recipients: list[str]) -> None:
        """Synchronous SMTP send (runs in executor to not block event loop)."""
        ctx = ssl.create_default_context() if (self.use_tls or self.use_ssl) else None
        if self.use_ssl and ctx:
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                self.host, self.port, context=ctx, timeout=self.timeout
            )
        else:
            server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
        with server:
            if self.use_tls and not self.use_ssl and ctx:
                server.starttls(context=ctx)
            if self.username and self.password:
                server.login(self.username, self.password)
            server.sendmail(mime["From"], recipients, mime.as_string())

    async def send(
        self, message: EmailMessage
    ) -> Result[MessageDeliveryReceipt, MailerError]:
        """Send an email via SMTP.

        Args:
            message: The email message to send.

        Returns:
            ``Ok(MessageDeliveryReceipt)`` on success.
            ``Err(SMTPMailerError)`` for SMTP delivery failures.
        """
        try:
            mime = self._build_mime(message)
            recipients = message.to + message.cc + message.bcc
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._send_sync, mime, recipients)
        except (smtplib.SMTPException, MessageError) as exc:
            # MessageError covers HeaderParseError/HeaderWriteError raised
            # by as_string() on CRLF-infiltrated headers (defense-in-depth:
            # EmailMessage validation rejects these at construction).
            logger.warning("smtp_send_failed", error=str(exc), host=self.host)
            return Err(SMTPMailerError(str(exc)))

        receipt = MessageDeliveryReceipt(
            message_id=str(uuid.uuid4()),
            backend="smtp",
            channel="email",
        )
        logger.info("smtp_sent", to=message.to, subject=message.subject)
        return Ok(receipt)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check SMTP connectivity by attempting a connection.

        Args:
            timeout: Max seconds to wait for the connection.

        Returns:
            :class:`~quadkit.contracts.core.HealthCheckResult`.
        """

        def _check() -> None:
            with smtplib.SMTP(self.host, self.port, timeout=timeout):
                pass

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _check)
            return HealthCheckResult(
                component="smtp",
                status=HealthStatus.HEALTHY,
                details={"host": self.host, "port": self.port},
            )
        except Exception as exc:  # noqa: BLE001 — health check must never raise
            return HealthCheckResult(
                component="smtp",
                status=HealthStatus.UNHEALTHY,
                details={"host": self.host, "error": str(exc)},
            )


__all__ = ["SMTPMailer"]


def _build_part(attachment: Attachment) -> MIMEBase:
    """One attachment as a base64 MIME part.

    ``content_id`` marks the part for inline reference from the HTML body
    (``<img src="cid:logo">``); without one the part is a download, named
    by ``filename``.
    """
    maintype, _, subtype = attachment.content_type.partition("/")
    part = MIMEBase(maintype or "application", subtype or "octet-stream")
    part.set_payload(attachment.content)
    encoders.encode_base64(part)
    disposition = "inline" if attachment.content_id else "attachment"
    part.add_header("Content-Disposition", disposition, filename=attachment.filename)
    if attachment.content_id:
        part.add_header("Content-ID", f"<{attachment.content_id}>")
    return part
