"""WhatsApp Business API notification backend.

Supports two delivery providers:

- **Twilio** — uses the Twilio Messaging API with the ``whatsapp:`` URI
  scheme.  Requires the existing ``aiohttp`` dependency.
- **Meta** — calls the Meta (Facebook) WhatsApp Business API directly
  via ``httpx``.  Requires the ``quadkit-notification[whatsapp]`` extra.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any
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

# Meta Graph API base URL for WhatsApp Business messages.
_META_API_BASE = "https://graph.facebook.com/v19.0"
_DEFAULT_META_TIMEOUT = 30


class WhatsAppNotificationError(TwilioNotificationError):
    """WhatsApp delivery failure via Twilio provider."""

    _code = "QK_ERR_NOTIF_012"

    def __init__(
        self,
        message: str = "WhatsApp (Twilio) delivery error",
        *,
        twilio_code: int | None = None,
        **kwargs: Any,
    ) -> None:
        # Call NotificationError directly; super chain reaches TwilioNotificationError
        # but we override backend to "whatsapp_twilio".
        super().__init__(message, twilio_code=twilio_code, **kwargs)
        self.backend = "whatsapp_twilio"


class WhatsAppMetaNotificationError(TwilioNotificationError):
    """WhatsApp delivery failure via Meta provider."""

    _code = "QK_ERR_NOTIF_013"

    def __init__(
        self,
        message: str = "WhatsApp (Meta) delivery error",
        *,
        meta_code: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.backend = "whatsapp_meta"
        self.meta_code = meta_code


class WhatsAppBackend:
    """WhatsApp Business API notification backend.

    Supports two providers:

    - ``"twilio"`` — Twilio Messaging API with ``whatsapp:`` prefix.
      Accepts the same ``account_sid`` / ``auth_token`` / ``from_number``
      credentials as :class:`~quadkit.notification.backends.sms.twilio.TwilioSMS`.
    - ``"meta"`` — Meta (Facebook) WhatsApp Business API.
      Requires ``access_token`` and ``phone_number_id``.

    Implements a compatible ``send`` / ``health_check`` interface.

    Args:
        provider: Delivery provider.  Either ``"twilio"`` or ``"meta"``.
        account_sid: Twilio Account SID (Twilio provider only).
        auth_token: Twilio Auth Token (Twilio provider only).
        from_number: Twilio WhatsApp-enabled number in ``whatsapp:+1…``
            format, or just the E.164 number (prefix added automatically).
        access_token: Meta Graph API access token (Meta provider only).
        phone_number_id: Meta phone number object ID (Meta provider only).
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        *,
        provider: str = "twilio",
        account_sid: str | None = None,
        auth_token: str | None = None,
        from_number: str | None = None,
        access_token: str | None = None,
        phone_number_id: str | None = None,
        timeout: int = DEFAULT_TWILIO_TIMEOUT,
    ) -> None:
        if provider not in ("twilio", "meta"):
            raise ValueError(
                f"Unsupported WhatsApp provider: {provider!r}. "
                "Expected 'twilio' or 'meta'."
            )
        self._provider = provider
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._from_number = from_number
        self._access_token = access_token
        self._phone_number_id = phone_number_id
        self._timeout = timeout

    # ──────────────────────────────────────────────────────────────
    # Public interface
    # ──────────────────────────────────────────────────────────────

    async def send(
        self, message: SMSMessage
    ) -> Result[MessageDeliveryReceipt, NotificationError]:
        """Send a WhatsApp message.

        Dispatches to the appropriate provider implementation.

        Args:
            message: The :class:`~quadkit.contracts.notification.types.SMSMessage`
                to deliver.  ``message.to`` must contain the recipient phone
                numbers in E.164 format.

        Returns:
            ``Ok(MessageDeliveryReceipt)`` on success.
            ``Err(NotificationError)`` on delivery failure.
        """
        if self._provider == "twilio":
            return await self._send_twilio(message)
        return await self._send_meta(message)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check provider API reachability.

        Args:
            timeout: Max seconds to wait.

        Returns:
            :class:`~quadkit.contracts.core.HealthCheckResult`.
        """
        if self._provider == "twilio":
            return await self._health_twilio(timeout)
        return await self._health_meta(timeout)

    # ──────────────────────────────────────────────────────────────
    # Twilio provider
    # ──────────────────────────────────────────────────────────────

    def _twilio_auth_header(self) -> str:
        """Build Basic Auth header for Twilio."""
        credentials = f"{self._account_sid}:{self._auth_token}"
        return "Basic " + base64.b64encode(credentials.encode()).decode()

    def _whatsapp_number(self, number: str) -> str:
        """Ensure the number has the ``whatsapp:`` prefix."""
        if number.startswith("whatsapp:"):
            return number
        return f"whatsapp:{number}"

    async def _send_twilio(
        self, message: SMSMessage
    ) -> Result[MessageDeliveryReceipt, NotificationError]:
        """Send via Twilio Messaging API."""
        import aiohttp

        url = f"{TWILIO_API_BASE}/Accounts/{self._account_sid}/Messages.json"
        headers = {
            "Authorization": self._twilio_auth_header(),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        from_wa = self._whatsapp_number(message.from_number or self._from_number or "")
        to_number = message.to[0] if message.to else ""
        data = {
            "To": self._whatsapp_number(to_number),
            "From": from_wa,
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
                        "whatsapp.twilio_non_json_response",
                        status=resp.status,
                        error=str(exc),
                    )
                    return Err(
                        WhatsAppNotificationError(
                            f"Non-JSON response from Twilio API: HTTP {resp.status}"
                        )
                    )
                if resp.status == 201:
                    receipt = MessageDeliveryReceipt(
                        message_id=str(uuid.uuid4()),
                        backend="whatsapp_twilio",
                        channel="whatsapp",
                        provider_reference=body.get("sid"),
                    )
                    logger.info(
                        "whatsapp.twilio_sent",
                        to=message.to,
                        sid=body.get("sid"),
                    )
                    return Ok(receipt)

                error_msg = body.get("message", f"HTTP {resp.status}")
                twilio_code = body.get("code")
                logger.warning(
                    "whatsapp.twilio_send_failed",
                    status=resp.status,
                    code=twilio_code,
                    message=error_msg,
                )
                return Err(
                    WhatsAppNotificationError(error_msg, twilio_code=twilio_code)
                )

    async def _health_twilio(self, timeout: float) -> HealthCheckResult:
        """Health check via Twilio Account API."""
        import aiohttp

        try:
            url = f"{TWILIO_API_BASE}/Accounts/{self._account_sid}.json"
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={"Authorization": self._twilio_auth_header()},
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    status = (
                        HealthStatus.HEALTHY
                        if resp.status < 500
                        else HealthStatus.UNHEALTHY
                    )
                    return HealthCheckResult(
                        component="whatsapp_twilio",
                        status=status,
                        details={"http_status": resp.status},
                    )
        except Exception as exc:  # noqa: BLE001 — health check must never raise
            return HealthCheckResult(
                component="whatsapp_twilio",
                status=HealthStatus.UNHEALTHY,
                details={"error": str(exc)},
            )

    # ──────────────────────────────────────────────────────────────
    # Meta provider
    # ──────────────────────────────────────────────────────────────

    async def _send_meta(
        self, message: SMSMessage
    ) -> Result[MessageDeliveryReceipt, NotificationError]:
        """Send via Meta WhatsApp Business API."""
        try:
            import httpx
        except ImportError as exc:
            raise ImportError(
                "httpx is required for the Meta WhatsApp provider. "
                "Install with: pip install quadkit-notification[whatsapp]"
            ) from exc

        url = f"{_META_API_BASE}/{self._phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        to_number = message.to[0] if message.to else ""
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": message.body},
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload, headers=headers)
            try:
                body = resp.json()
            except Exception as exc:  # noqa: BLE001 — non-JSON body is a failure
                logger.warning(
                    "whatsapp.meta_non_json_response",
                    status=resp.status_code,
                    error=str(exc),
                )
                return Err(
                    WhatsAppMetaNotificationError(
                        f"Non-JSON response from Meta API: HTTP {resp.status_code}"
                    )
                )
            if resp.status_code == 200:
                messages = body.get("messages", [{}])
                wa_id = messages[0].get("id") if messages else None
                receipt = MessageDeliveryReceipt(
                    message_id=str(uuid.uuid4()),
                    backend="whatsapp_meta",
                    channel="whatsapp",
                    provider_reference=wa_id,
                )
                logger.info(
                    "whatsapp.meta_sent",
                    to=message.to,
                    wa_id=wa_id,
                )
                return Ok(receipt)

            error = body.get("error", {})
            error_msg = error.get("message", f"HTTP {resp.status_code}")
            meta_code = str(error.get("code", "")) or None
            logger.warning(
                "whatsapp.meta_send_failed",
                status=resp.status_code,
                error=error_msg,
                code=meta_code,
            )
            return Err(WhatsAppMetaNotificationError(error_msg, meta_code=meta_code))

    async def _health_meta(self, timeout: float) -> HealthCheckResult:
        """Health check via Meta Graph API token debug endpoint."""
        try:
            import httpx
        except ImportError:
            return HealthCheckResult(
                component="whatsapp_meta",
                status=HealthStatus.UNHEALTHY,
                message="httpx is not installed",
            )

        try:
            url = (
                f"https://graph.facebook.com/debug_token"
                f"?input_token={self._access_token}"
                f"&access_token={self._access_token}"
            )
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(url)
                status = (
                    HealthStatus.HEALTHY
                    if resp.status_code < 500
                    else HealthStatus.UNHEALTHY
                )
                return HealthCheckResult(
                    component="whatsapp_meta",
                    status=status,
                    details={"http_status": resp.status_code},
                )
        except Exception as exc:  # noqa: BLE001 — health check must never raise
            return HealthCheckResult(
                component="whatsapp_meta",
                status=HealthStatus.UNHEALTHY,
                details={"error": str(exc)},
            )


__all__ = [
    "WhatsAppBackend",
    "WhatsAppMetaNotificationError",
    "WhatsAppNotificationError",
]
