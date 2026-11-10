"""Web Push (RFC 8030) notification backend using VAPID + encryption."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
import uuid

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.mailer import MessageDeliveryReceipt
from quadkit.contracts.notification.types import PushMessage
from quadkit.logging import get_logger
from quadkit.notification.exceptions import WebPushNotificationError
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.notification.errors import NotificationError

logger = get_logger(__name__)

try:
    from pywebpush import WebPushException, webpush  # type: ignore[import-untyped]
except ImportError:
    WebPushException = Exception

    def webpush(*args: object, **kwargs: object) -> None:
        raise ImportError(
            "pywebpush is not installed. Install quadkit-notification[web-push]."
        )


_HTTP_CLIENT_TIMEOUT = 30


class WebPushChannel:
    """Web Push (RFC 8030) notification backend.

    Implements :class:`~quadkit.contracts.notification.protocols.PushChannelProtocol`.
    Uses VAPID (RFC 8292) for application-level authentication and RFC 8291
    (aes128gcm) for message encryption.

    Requires the ``pywebpush`` optional extra.

    Args:
        vapid_private_key: VAPID private key (PEM-encoded EC prime256v1).
        vapid_public_key: VAPID public key (base64url-encoded).
        vapid_claims_subject: Contact URI for VAPID claims
            (e.g. ``"mailto:ops@example.com"``).
        http_timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        vapid_private_key: str,
        vapid_public_key: str,
        vapid_claims_subject: str,
        http_timeout: int = _HTTP_CLIENT_TIMEOUT,
    ) -> None:
        self._vapid_private_key = vapid_private_key
        self._vapid_public_key = vapid_public_key
        self._vapid_claims_subject = vapid_claims_subject
        self._http_timeout = http_timeout

    async def send(
        self, message: PushMessage
    ) -> Result[MessageDeliveryReceipt, NotificationError]:
        """Send a Web Push notification.

        ``message.to`` contains a list of **endpoint URLs** (not device tokens).
        Each endpoint is a separate push subscription.

        Args:
            message: The push notification to deliver. ``message.to`` must
                contain at least one endpoint URL.

        Returns:
            Ok(MessageDeliveryReceipt) on success.
            Err(WebPushNotificationError) for delivery failures.
        """
        if not message.to:
            raise ValueError("WebPushChannel.send() requires at least one endpoint")

        from quadkit.serialization import dumps_str

        payload: dict[str, object] = {
            "title": message.title,
            "body": message.body,
        }
        if message.data:
            payload["data"] = message.data
        if message.badge is not None:
            payload["badge"] = message.badge
        if message.image:
            payload["icon"] = message.image

        endpoint = message.to[0]

        try:
            subscription_info: dict[str, object] = {"endpoint": endpoint}

            keys = (message.data or {}).get("keys")
            if isinstance(keys, dict):
                p256dh = keys.get("p256dh", "")
                auth = keys.get("auth", "")
                if p256dh and auth:
                    subscription_info["keys"] = {"p256dh": p256dh, "auth": auth}

            result = webpush(
                subscription_info=subscription_info,
                data=dumps_str(payload),
                vapid_private_key=self._vapid_private_key,
                vapid_public_key=self._vapid_public_key,
                vapid_claims={"sub": self._vapid_claims_subject},
                ttl=message.ttl or 0,
                timeout=self._http_timeout,
            )

            receipt = MessageDeliveryReceipt(
                message_id=str(uuid.uuid4()),
                backend="web_push",
                channel="push",
                provider_reference=endpoint[:64],
            )
            logger.info(
                "webpush_sent",
                endpoint_prefix=endpoint[:48],
                status_code=result.status_code
                if hasattr(result, "status_code")
                else None,
            )
            return Ok(receipt)

        except WebPushException as exc:
            status_code = getattr(exc, "status_code", None)
            response_body = getattr(exc, "response_body", None)
            logger.warning(
                "webpush_send_failed",
                endpoint_prefix=endpoint[:48],
                status_code=status_code,
                response=response_body,
            )

            if status_code in (410, 404):
                return Err(
                    WebPushNotificationError(
                        message=f"Subscription gone (HTTP {status_code})",
                        status_code=status_code,
                        reason="subscription_gone",
                    )
                )

            return Err(
                WebPushNotificationError(
                    message=str(exc),
                    status_code=status_code or 0,
                    reason=response_body or "webpush_error",
                )
            )

    async def send_batch(
        self, messages: list[PushMessage]
    ) -> list[Result[MessageDeliveryReceipt, NotificationError]]:
        """Send multiple Web Push notifications concurrently.

        Args:
            messages: Notifications to deliver.

        Returns:
            List of Result values, one per message, order preserved.
        """
        tasks = [self.send(msg) for msg in messages]
        return await asyncio.gather(*tasks)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check Web Push infrastructure availability.

        Since Web Push has no global health endpoint, this is a best-effort
        check that verifies the VAPID key is loadable.

        Args:
            timeout: Max seconds to wait (unused, but kept for protocol compat).

        Returns:
            HealthCheckResult.
        """
        if not self._vapid_private_key or not self._vapid_private_key.strip():
            return HealthCheckResult(
                component="web_push",
                status=HealthStatus.DEGRADED,
                details={"vapid_configured": False},
            )
        try:
            from cryptography.hazmat.primitives.asymmetric import ec
            from py_vapid import Vapid  # type: ignore[import-untyped]

            raw_key = self._vapid_private_key.strip()
            v = (
                Vapid.from_pem(raw_key.encode())
                if "BEGIN" in raw_key
                else Vapid.from_string(raw_key)
            )
            private_key_obj = v.private_key
            if not isinstance(private_key_obj, ec.EllipticCurvePrivateKey):
                return HealthCheckResult(
                    component="web_push",
                    status=HealthStatus.UNHEALTHY,
                    details={"error": "VAPID key is not an EC key"},
                )
            return HealthCheckResult(
                component="web_push",
                status=HealthStatus.HEALTHY,
                details={"vapid_key_valid": True},
            )
        except Exception as exc:  # noqa: BLE001
            return HealthCheckResult(
                component="web_push",
                status=HealthStatus.UNHEALTHY,
                details={"error": str(exc)},
            )


__all__ = ["WebPushChannel"]
