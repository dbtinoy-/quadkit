"""FCM (Firebase Cloud Messaging) push notification backend."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
import uuid

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.mailer import MessageDeliveryReceipt
from quadkit.contracts.notification.types import PushMessage
from quadkit.logging import get_logger
from quadkit.notification.constants import DEFAULT_FCM_TIMEOUT, FCM_SEND_URL
from quadkit.notification.exceptions import FCMNotificationError
from quadkit.result import Err, Ok, Result

if TYPE_CHECKING:
    from quadkit.contracts.notification.errors import NotificationError

logger = get_logger(__name__)


class FCMPush:
    """Push notification backend that sends via Firebase Cloud Messaging (FCM).

    Implements :class:`~quadkit.contracts.notification.protocols.PushChannelProtocol`.
    Requires the ``aiohttp`` optional extra.

    Args:
        server_key: FCM Server API Key.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        server_key: str,
        timeout: int = DEFAULT_FCM_TIMEOUT,
    ) -> None:
        self._server_key = server_key
        self._timeout = timeout

    async def send(
        self, message: PushMessage
    ) -> Result[MessageDeliveryReceipt, NotificationError]:
        """Send a push notification via FCM REST API.

        Args:
            message: The push notification to deliver.

        Returns:
            ``Ok(MessageDeliveryReceipt)`` on success.
            ``Err(FCMNotificationError)`` for failures.

        Raises:
            aiohttp.ClientError: For network connectivity issues.
            OSError: For low-level socket/infrastructure errors.
        """
        import aiohttp

        headers = {
            "Authorization": f"key={self._server_key}",
            "Content-Type": "application/json",
        }

        # Build FCM notification payload
        payload: dict[str, Any] = {
            "registration_ids": message.to,
            "notification": {
                "title": message.title,
                "body": message.body,
            },
        }

        # Add optional fields
        if message.data:
            payload["data"] = message.data
        if message.image:
            payload["notification"]["image"] = message.image
        if message.sound:
            payload["notification"]["sound"] = message.sound
        if message.badge is not None:
            payload["notification"]["badge"] = message.badge
        if message.ttl is not None:
            payload["time_to_live"] = message.ttl

        async with aiohttp.ClientSession() as session:
            async with session.post(
                FCM_SEND_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                try:
                    body = await resp.json()
                except Exception as exc:  # noqa: BLE001 — non-JSON body is a failure
                    logger.warning(
                        "fcm_non_json_response",
                        status=resp.status,
                        error=str(exc),
                    )
                    return Err(
                        FCMNotificationError(
                            f"Non-JSON response from FCM API: HTTP {resp.status}"
                        )
                    )

                if resp.status == 200:
                    results = body.get("results", [])
                    if results and "error" not in results[0]:
                        message_id = results[0].get("message_id")
                        receipt = MessageDeliveryReceipt(
                            message_id=str(uuid.uuid4()),
                            backend="fcm",
                            channel="push",
                            provider_reference=message_id,
                        )
                        logger.info(
                            "fcm_sent",
                            to=message.to,
                            fcm_msg_id=message_id,
                            success=body.get("success", 0),
                        )
                        return Ok(receipt)

                    # Handle FCM error in results
                    if results:
                        fcm_error = results[0].get("error", "Unknown error")
                        logger.warning(
                            "fcm_send_failed",
                            status=resp.status,
                            error=fcm_error,
                            failure_count=body.get("failure", 0),
                        )
                        return Err(
                            FCMNotificationError(
                                f"FCM error: {fcm_error}",
                                fcm_error=fcm_error,
                            )
                        )

                # Handle non-200 HTTP status
                error_msg = body.get("error", f"HTTP {resp.status}")
                logger.warning("fcm_send_failed", status=resp.status, body=body)
                return Err(FCMNotificationError(error_msg))

    async def send_batch(
        self, messages: list[PushMessage]
    ) -> list[Result[MessageDeliveryReceipt, NotificationError]]:
        """Send multiple push notifications in parallel.

        Args:
            messages: List of push notifications to deliver.

        Returns:
            List of ``Result`` values, one per message, preserving order.
        """
        tasks = [self.send(msg) for msg in messages]
        return await asyncio.gather(*tasks)

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check FCM API reachability.

        Args:
            timeout: Max seconds to wait.

        Returns:
            :class:`~quadkit.contracts.core.HealthCheckResult`.
        """
        import aiohttp

        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(
                    FCM_SEND_URL,
                    headers={"Authorization": f"key={self._server_key}"},
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    status = (
                        HealthStatus.HEALTHY
                        if resp.status < 500
                        else HealthStatus.UNHEALTHY
                    )
                    return HealthCheckResult(
                        component="fcm",
                        status=status,
                        details={"http_status": resp.status},
                    )
        except Exception as exc:  # noqa: BLE001 — health check must never raise
            return HealthCheckResult(
                component="fcm",
                status=HealthStatus.UNHEALTHY,
                details={"error": str(exc)},
            )


__all__ = ["FCMPush"]
