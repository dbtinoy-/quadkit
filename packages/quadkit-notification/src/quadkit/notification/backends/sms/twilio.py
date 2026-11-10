"""Twilio SMS backend."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING
import uuid

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.mailer import MessageDeliveryReceipt
from quadkit.contracts.notification.types import SMSMessage
from quadkit.logging import get_logger
from quadkit.notification.constants import DEFAULT_TWILIO_TIMEOUT, TWILIO_API_BASE
from quadkit.notification.exceptions import TwilioNotificationError
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.notification.errors import NotificationError

logger = get_logger(__name__)


class TwilioSMS:
    """SMS backend that sends via Twilio REST API.

    Implements :class:`~quadkit.contracts.notification.protocols.SMSChannelProtocol`.
    Requires the ``aiohttp`` optional extra.

    Args:
        account_sid: Twilio Account SID.
        auth_token: Twilio Auth Token.
        from_number: Twilio phone number in E.164 format (e.g., +15550000000).
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        account_sid: str,
        auth_token: str,
        from_number: str | None = None,
        timeout: int = DEFAULT_TWILIO_TIMEOUT,
    ) -> None:
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from_number = from_number
        self._timeout = timeout

    def _get_auth_header(self) -> str:
        """Generate Basic Auth header for Twilio."""
        credentials = f"{self._account_sid}:{self._auth_token}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    async def send(
        self, message: SMSMessage
    ) -> Result[MessageDeliveryReceipt, NotificationError]:
        """Send an SMS via the Twilio REST API.

        Args:
            message: The SMS to deliver.

        Returns:
            ``Ok(MessageDeliveryReceipt)`` on HTTP 201.
            ``Err(TwilioNotificationError)`` for 4xx/5xx responses.

        Raises:
            aiohttp.ClientError: For network connectivity issues.
            OSError: For low-level socket/infrastructure errors.
        """
        import aiohttp

        url = f"{TWILIO_API_BASE}/Accounts/{self._account_sid}/Messages.json"
        headers = {
            "Authorization": self._get_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
        }

        # Build form data
        from_number = message.from_number or self._from_number
        data = {
            "To": message.to[0] if message.to else "",
            "From": from_number,
            "Body": message.body,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                data=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                try:
                    body = await resp.json()
                except Exception as exc:  # noqa: BLE001 — non-JSON body is a failure
                    logger.warning(
                        "twilio_non_json_response",
                        status=resp.status,
                        error=str(exc),
                    )
                    return Err(
                        TwilioNotificationError(
                            f"Non-JSON response from Twilio API: HTTP {resp.status}"
                        )
                    )

                if resp.status == 201:
                    receipt = MessageDeliveryReceipt(
                        message_id=str(uuid.uuid4()),
                        backend="twilio",
                        channel="sms",
                        provider_reference=body.get("sid"),
                    )
                    logger.info("twilio_sent", to=message.to, sid=body.get("sid"))
                    return Ok(receipt)

                # Handle error response
                error_msg = body.get("message", f"HTTP {resp.status}")
                twilio_code = body.get("code")
                logger.warning(
                    "twilio_send_failed",
                    status=resp.status,
                    code=twilio_code,
                    message=error_msg,
                )
                return Err(TwilioNotificationError(error_msg, twilio_code=twilio_code))

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check Twilio API reachability.

        Args:
            timeout: Max seconds to wait.

        Returns:
            :class:`~quadkit.contracts.core.HealthCheckResult`.
        """
        import aiohttp

        try:
            url = f"{TWILIO_API_BASE}/Accounts/{self._account_sid}.json"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={"Authorization": self._get_auth_header()},
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    status = (
                        HealthStatus.HEALTHY
                        if resp.status < 500
                        else HealthStatus.UNHEALTHY
                    )
                    return HealthCheckResult(
                        component="twilio",
                        status=status,
                        details={"http_status": resp.status},
                    )
        except Exception as exc:  # noqa: BLE001 — health check must never raise
            return HealthCheckResult(
                component="twilio",
                status=HealthStatus.UNHEALTHY,
                details={"error": str(exc)},
            )


__all__ = ["TwilioSMS"]
