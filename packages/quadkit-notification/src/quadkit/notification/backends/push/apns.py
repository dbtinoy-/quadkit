"""APNs (Apple Push Notification service) push notification backend."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING
import uuid

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.mailer import MessageDeliveryReceipt
from quadkit.contracts.notification.types import PushMessage
from quadkit.logging import get_logger
from quadkit.notification.constants import (
    APNS_BASE_URL,
    APNS_SANDBOX_URL,
    DEFAULT_APNS_TIMEOUT,
)
from quadkit.notification.exceptions import APNsNotificationError
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.notification.errors import NotificationError

logger = get_logger(__name__)


class APNsPush:
    """Apple Push Notification service backend.

    Implements :class:`~quadkit.contracts.notification.protocols.PushChannelProtocol`.
    Uses the APNs HTTP/2 REST API with JWT authentication.
    Requires the ``httpx[http2]`` and ``PyJWT`` optional extras.

    Args:
        team_id: Apple Developer Team ID (10-character string).
        key_id: APNs Auth Key ID (10-character string).
        apns_auth_key: ECDSA private key — either a PEM string starting with
            ``-----BEGIN PRIVATE KEY-----`` or a filesystem path to a ``.p8``
            key file downloaded from the Apple Developer portal.
        bundle_id: App bundle identifier (e.g. ``com.example.MyApp``).
            Used as the ``apns-topic`` header value.
        sandbox: Send via the APNs sandbox endpoint. Defaults to ``False``
            (production).
        timeout: HTTP request timeout in seconds. Defaults to 30.
    """

    def __init__(
        self,
        team_id: str,
        key_id: str,
        apns_auth_key: str,
        bundle_id: str,
        sandbox: bool = False,
        timeout: int = DEFAULT_APNS_TIMEOUT,
    ) -> None:
        self._team_id = team_id
        self._key_id = key_id
        self._apns_auth_key = apns_auth_key
        self._bundle_id = bundle_id
        self._sandbox = sandbox
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_private_key(self) -> str:
        """Return the raw PEM key string, loading from disk if necessary."""
        stripped = self._apns_auth_key.strip()
        if stripped.startswith("-----BEGIN"):
            return stripped
        # Treat as a filesystem path to a .p8 key file.
        with open(stripped) as fh:  # noqa: PTH123
            return fh.read()

    def _make_jwt(self) -> str:
        """Generate a signed ES256 JWT token for APNs bearer authentication."""
        import jwt

        key_data = self._load_private_key()
        issued_at = int(time.time())
        payload = {"iss": self._team_id, "iat": issued_at}
        # PyJWT merges extra_headers into the JWT header block.
        return jwt.encode(
            payload,
            key_data,
            algorithm="ES256",
            headers={"kid": self._key_id},
        )

    async def _send_to_token(
        self,
        device_token: str,
        message: PushMessage,
    ) -> Result[MessageDeliveryReceipt, NotificationError]:
        """Deliver one push notification to a single APNs device token."""
        import httpx

        base_url = APNS_SANDBOX_URL if self._sandbox else APNS_BASE_URL
        url = f"{base_url}/3/device/{device_token}"
        jwt_token = self._make_jwt()

        headers = {
            "authorization": f"bearer {jwt_token}",
            "apns-topic": self._bundle_id,
            "apns-push-type": "alert",
        }

        # Build the APS dictionary
        aps: dict[str, object] = {
            "alert": {
                "title": message.title,
                "body": message.body,
            }
        }
        if message.badge is not None:
            aps["badge"] = message.badge
        if message.sound:
            aps["sound"] = message.sound

        # Root payload: aps + optional custom data keys
        payload: dict[str, object] = {"aps": aps}
        if message.data:
            payload.update(message.data)

        try:
            async with httpx.AsyncClient(
                http2=True,
                timeout=float(self._timeout),
            ) as client:
                resp = await client.post(url, json=payload, headers=headers)

                if resp.status_code == 200:
                    apns_id = resp.headers.get("apns-id")
                    receipt = MessageDeliveryReceipt(
                        message_id=str(uuid.uuid4()),
                        backend="apns",
                        channel="push",
                        provider_reference=apns_id,
                    )
                    logger.info(
                        "apns_sent",
                        token_prefix=device_token[:8],
                        apns_id=apns_id,
                        bundle_id=self._bundle_id,
                        sandbox=self._sandbox,
                    )
                    return Ok(receipt)

                # Non-200: APNs returns JSON with a ``reason`` field.
                try:
                    body = resp.json()
                    reason: str = body.get("reason", f"HTTP {resp.status_code}")
                except Exception:  # noqa: BLE001  # JSON parse failures are non-fatal
                    reason = f"HTTP {resp.status_code}"

                logger.warning(
                    "apns_send_failed",
                    token_prefix=device_token[:8],
                    status=resp.status_code,
                    reason=reason,
                    sandbox=self._sandbox,
                )
                return Err(APNsNotificationError(reason, apns_reason=reason))

        except OSError as exc:
            logger.warning(
                "apns_network_error",
                token_prefix=device_token[:8],
                error=str(exc),
            )
            return Err(APNsNotificationError(f"Network error: {exc}"))

    # ------------------------------------------------------------------
    # Public API (PushChannelProtocol)
    # ------------------------------------------------------------------

    async def send(
        self,
        message: PushMessage,
    ) -> Result[MessageDeliveryReceipt, NotificationError]:
        """Send a push notification via the APNs HTTP/2 API.

        APNs accepts one device token per HTTP request.  This method targets
        ``message.to[0]``.  Use :meth:`send_batch` to fan-out a single message
        payload to multiple tokens concurrently.

        Args:
            message: The push notification to deliver.  ``message.to`` must
                contain at least one device token.

        Returns:
            ``Ok(MessageDeliveryReceipt)`` on HTTP 200.
            ``Err(APNsNotificationError)`` for any APNs or network failure.

        Raises:
            ValueError: If ``message.to`` is empty.
        """
        if not message.to:
            raise ValueError("APNsPush.send() requires at least one device token")
        return await self._send_to_token(message.to[0], message)

    async def send_batch(
        self,
        messages: list[PushMessage],
    ) -> list[Result[MessageDeliveryReceipt, NotificationError]]:
        """Send multiple push notifications concurrently.

        Each :class:`~quadkit.contracts.notification.types.PushMessage` in
        *messages* is dispatched to the first token in its ``to`` list.

        Args:
            messages: Notifications to deliver.

        Returns:
            ``Result`` list, one entry per message, order preserved.
        """
        tasks = [self.send(msg) for msg in messages]
        return await asyncio.gather(*tasks)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Verify APNs endpoint reachability via a HEAD request.

        Args:
            timeout: Maximum seconds to wait for a response.

        Returns:
            :class:`~quadkit.contracts.core.HealthCheckResult`.
        """
        import httpx

        base_url = APNS_SANDBOX_URL if self._sandbox else APNS_BASE_URL
        try:
            async with httpx.AsyncClient(http2=True, timeout=timeout) as client:
                resp = await client.head(base_url)
            status = (
                HealthStatus.HEALTHY
                if resp.status_code < 500
                else HealthStatus.UNHEALTHY
            )
            return HealthCheckResult(
                component="apns",
                status=status,
                details={
                    "http_status": resp.status_code,
                    "sandbox": self._sandbox,
                },
            )
        except Exception as exc:  # noqa: BLE001 — health check must never raise
            return HealthCheckResult(
                component="apns",
                status=HealthStatus.UNHEALTHY,
                details={"error": str(exc), "sandbox": self._sandbox},
            )


__all__ = ["APNsPush"]
