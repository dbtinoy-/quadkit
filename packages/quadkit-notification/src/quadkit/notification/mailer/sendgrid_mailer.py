"""SendGrid email backend."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import uuid

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.mailer import (
    EmailMessage,
    MessageDeliveryReceipt,
)
from quadkit.logging import get_logger
from quadkit.notification.constants import DEFAULT_FROM_EMAIL, SENDGRID_API_URL
from quadkit.notification.exceptions import SendGridMailerError
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.mailer.errors import MailerError

logger = get_logger(__name__)


class SendGridMailer:
    """Email backend that sends via SendGrid REST API v3.

    Implements :class:`~quadkit.contracts.mailer.protocols.MailerProtocol`.
    Requires the ``aiohttp`` optional extra.

    Args:
        api_key: SendGrid API key (``SG.*``).
        timeout: HTTP request timeout in seconds.
        sandbox_mode: When ``True``, emails are not actually delivered.
        from_email: Default sender email address.
        from_name: Default sender display name.
    """

    def __init__(
        self,
        api_key: str,
        timeout: int = 30,
        sandbox_mode: bool = False,
        from_email: str | None = None,
        from_name: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._sandbox_mode = sandbox_mode
        self.from_email = from_email or DEFAULT_FROM_EMAIL
        self.from_name = from_name

    def _build_payload(self, message: EmailMessage) -> dict[str, Any]:
        """Build SendGrid Mail Send API v3 JSON payload."""
        sender_email = message.from_email or self.from_email
        sender_name = message.from_name or self.from_name
        from_obj: dict[str, Any] = {"email": sender_email}
        if sender_name:
            from_obj["name"] = sender_name

        content = []
        if message.body:
            content.append({"type": "text/plain", "value": message.body})
        if message.html_body:
            content.append({"type": "text/html", "value": message.html_body})

        payload: dict[str, Any] = {
            "personalizations": [{"to": [{"email": r} for r in message.to]}],
            "from": from_obj,
            "subject": message.subject,
            "content": content,
        }

        if message.cc:
            payload["personalizations"][0]["cc"] = [{"email": r} for r in message.cc]
        if message.bcc:
            payload["personalizations"][0]["bcc"] = [{"email": r} for r in message.bcc]
        if self._sandbox_mode:
            payload["mail_settings"] = {"sandbox_mode": {"enable": True}}

        return payload

    async def send(
        self, message: EmailMessage
    ) -> Result[MessageDeliveryReceipt, MailerError]:
        """Send an email via the SendGrid REST API.

        Args:
            message: The email to deliver.

        Returns:
            ``Ok(MessageDeliveryReceipt)`` on HTTP 202.
            ``Err(SendGridMailerError)`` for 4xx/5xx responses.

        Raises:
            aiohttp.ClientError: For network connectivity issues (DNS, connection refused).
            OSError: For low-level socket/infrastructure errors.

        Note:
            Infrastructure errors propagate to enable retry and circuit-breaker logic
            at higher levels. Only HTTP-level errors are wrapped in the Result type.
        """
        import aiohttp

        payload = self._build_payload(message)
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                SENDGRID_API_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                if resp.status == 202:
                    provider_ref = resp.headers.get("X-Message-Id")
                    receipt = MessageDeliveryReceipt(
                        message_id=str(uuid.uuid4()),
                        backend="sendgrid",
                        channel="email",
                        provider_reference=provider_ref,
                    )
                    logger.info("sendgrid_sent", to=message.to, msg_id=provider_ref)
                    return Ok(receipt)

                body = await resp.json()
                errors = body.get("errors", [])
                error_msg = errors[0]["message"] if errors else f"HTTP {resp.status}"
                logger.warning("sendgrid_send_failed", status=resp.status, body=body)
                return Err(SendGridMailerError(error_msg, status_code=resp.status))

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check SendGrid API reachability.

        Args:
            timeout: Max seconds to wait.

        Returns:
            :class:`~quadkit.contracts.core.HealthCheckResult`.
        """
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    SENDGRID_API_URL,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    status = (
                        HealthStatus.HEALTHY
                        if resp.status < 500
                        else HealthStatus.UNHEALTHY
                    )
                    return HealthCheckResult(
                        component="sendgrid",
                        status=status,
                        details={"http_status": resp.status},
                    )
        except Exception as exc:  # noqa: BLE001 — health check must never raise
            return HealthCheckResult(
                component="sendgrid",
                status=HealthStatus.UNHEALTHY,
                details={"error": str(exc)},
            )


__all__ = ["SendGridMailer"]
