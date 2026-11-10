"""Slack notification backend.

Supports two delivery modes:

- **Webhook** — posts a message to a Slack Incoming Webhook URL via
  ``httpx``.  No dependency on the Slack SDK.
- **Bot API** — uses the ``slack-sdk`` ``AsyncWebClient`` to send rich
  messages, attach blocks, target specific channels, and reply in threads.
  Requires the ``quadkit-notification[slack]`` extra.
"""

from __future__ import annotations

from typing import Any
import uuid

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.mailer import MessageDeliveryReceipt
from quadkit.contracts.notification.errors import NotificationError
from quadkit.logging import get_logger
from quadkit.result import Err, Ok, Result

logger = get_logger(__name__)

_DEFAULT_TIMEOUT = 30

_MRKDWN_ESCAPES = str.maketrans({"<": "&lt;", ">": "&gt;", "&": "&amp;"})


def _escape_mrkdwn(text: str) -> str:
    """Escape Slack mrkdwn-special characters in user-supplied text.

    Slack interprets ``<url|label>`` link markup and ``&`` entities in the
    ``text`` field. Apply before sending untrusted content so it renders as
    literal text instead of a spoofable link.

    Args:
        text: Message text.

    Returns:
        Text with ``<``, ``>``, and ``&`` escaped.
    """
    return text.translate(_MRKDWN_ESCAPES)


class SlackNotificationError(NotificationError):
    """Slack notification delivery failure."""

    _code = "QK_ERR_NOTIF_014"

    def __init__(
        self,
        message: str = "Slack delivery error",
        *,
        slack_error: str | None = None,
    ) -> None:
        super().__init__(message, channel="chat", backend="slack")
        self.slack_error = slack_error


class SlackMessage:
    """A message to be delivered via Slack.

    Args:
        text: Plaintext fallback message body.
        channel: Target channel or user ID (Bot API only).  Overrides
            the ``default_channel`` set on the backend.
        blocks: Optional Block Kit blocks for rich formatting.
        thread_ts: Optional parent message timestamp for threaded replies.
    """

    __slots__ = ("blocks", "channel", "text", "thread_ts")

    def __init__(
        self,
        text: str,
        *,
        channel: str | None = None,
        blocks: list[dict[str, Any]] | None = None,
        thread_ts: str | None = None,
    ) -> None:
        self.text = text
        self.channel = channel
        self.blocks = blocks
        self.thread_ts = thread_ts


class SlackNotifier:
    """Slack notification backend.

    Supports two delivery modes:

    - **Incoming Webhook** (``mode="webhook"``): Posts a message to a
      pre-configured webhook URL.  Simple and credential-free; does not
      require ``slack-sdk``.  Uses ``httpx``.
    - **Bot API** (``mode="bot"``): Uses the ``slack-sdk``
      ``AsyncWebClient`` to send to any channel or user, with support
      for Block Kit, threading, and other rich features.  Requires the
      ``quadkit-notification[slack]`` extra.

    Args:
        webhook_url: Slack Incoming Webhook URL (webhook mode).
        bot_token: Slack Bot OAuth token beginning with ``xoxb-``
            (bot mode).
        default_channel: Default channel / user to message when
            :class:`SlackMessage` does not specify one (bot mode).
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        *,
        webhook_url: str | None = None,
        bot_token: str | None = None,
        default_channel: str | None = None,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        if not webhook_url and not bot_token:
            raise ValueError(
                "SlackNotifier requires either webhook_url (webhook mode) "
                "or bot_token (bot mode)."
            )
        self._webhook_url = webhook_url
        self._bot_token = bot_token
        self._default_channel = default_channel
        self._timeout = timeout

    @property
    def _mode(self) -> str:
        """Active delivery mode."""
        return "webhook" if self._webhook_url else "bot"

    # ──────────────────────────────────────────────────────────────
    # Public interface
    # ──────────────────────────────────────────────────────────────

    async def send(
        self, message: SlackMessage
    ) -> Result[MessageDeliveryReceipt, NotificationError]:
        """Send a Slack message.

        Dispatches to the webhook or Bot API implementation depending on
        which credentials were supplied at construction time.

        Args:
            message: :class:`SlackMessage` to deliver.

        Returns:
            ``Ok(MessageDeliveryReceipt)`` on success.
            ``Err(SlackNotificationError)`` on delivery failure.
        """
        if self._mode == "webhook":
            return await self._send_webhook(message)
        return await self._send_bot(message)

    async def send_text(
        self,
        text: str,
        *,
        channel: str | None = None,
        thread_ts: str | None = None,
    ) -> Result[MessageDeliveryReceipt, NotificationError]:
        """Convenience wrapper that sends a plain-text Slack message.

        Args:
            text: Message body.
            channel: Target channel (bot mode only).
            thread_ts: Thread parent timestamp for threaded replies.

        Returns:
            ``Ok(MessageDeliveryReceipt)`` on success.
        """
        return await self.send(SlackMessage(text, channel=channel, thread_ts=thread_ts))

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check Slack API reachability.

        - Webhook mode: performs a GET to ``https://slack.com``.
        - Bot API mode: calls ``auth.test`` with the bot token.

        Args:
            timeout: Max seconds to wait.

        Returns:
            :class:`~quadkit.contracts.core.HealthCheckResult`.
        """
        if self._mode == "webhook":
            return await self._health_webhook(timeout)
        return await self._health_bot(timeout)

    # ──────────────────────────────────────────────────────────────
    # Webhook mode
    # ──────────────────────────────────────────────────────────────

    async def _send_webhook(
        self, message: SlackMessage
    ) -> Result[MessageDeliveryReceipt, NotificationError]:
        """Post to a Slack Incoming Webhook URL via httpx."""
        try:
            import httpx
        except ImportError as exc:
            raise ImportError(
                "httpx is required for SlackNotifier webhook mode. "
                "Install with: pip install quadkit-notification[slack]"
            ) from exc

        payload: dict[str, Any] = {"text": _escape_mrkdwn(message.text)}
        if message.blocks:
            payload["blocks"] = message.blocks

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                self._webhook_url,  # type: ignore[arg-type]
                json=payload,
            )

        # Slack webhooks return 200 with plain-text ``"ok"`` on success.
        if resp.status_code == 200 and resp.text.strip() == "ok":
            receipt = MessageDeliveryReceipt(
                message_id=str(uuid.uuid4()),
                backend="slack_webhook",
                channel="slack",
            )
            logger.info("slack.webhook_sent", text_preview=message.text[:50])
            return Ok(receipt)

        error_text = resp.text.strip() or f"HTTP {resp.status_code}"
        logger.warning(
            "slack.webhook_send_failed",
            status=resp.status_code,
            body=error_text,
        )
        return Err(
            SlackNotificationError(
                f"Slack webhook error: {error_text}",
                slack_error=error_text,
            )
        )

    async def _health_webhook(self, timeout: float) -> HealthCheckResult:
        """Lightweight connectivity check for webhook mode."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get("https://slack.com")
                status = (
                    HealthStatus.HEALTHY
                    if resp.status_code < 500
                    else HealthStatus.UNHEALTHY
                )
                return HealthCheckResult(
                    component="slack_webhook",
                    status=status,
                    details={"http_status": resp.status_code},
                )
        except Exception as exc:  # noqa: BLE001 — health check must never raise
            return HealthCheckResult(
                component="slack_webhook",
                status=HealthStatus.UNHEALTHY,
                details={"error": str(exc)},
            )

    # ──────────────────────────────────────────────────────────────
    # Bot API mode
    # ──────────────────────────────────────────────────────────────

    async def _send_bot(
        self, message: SlackMessage
    ) -> Result[MessageDeliveryReceipt, NotificationError]:
        """Send via slack-sdk AsyncWebClient."""
        try:
            from slack_sdk.web.async_client import (  # type: ignore[import-not-found]
                AsyncWebClient,
            )
        except ImportError as exc:
            raise ImportError(
                "slack-sdk is required for SlackNotifier bot mode. "
                "Install with: pip install quadkit-notification[slack]"
            ) from exc

        channel = message.channel or self._default_channel
        if not channel:
            return Err(
                SlackNotificationError(
                    "SlackNotifier bot mode requires a channel. "
                    "Set default_channel or pass message.channel.",
                    slack_error="missing_channel",
                )
            )

        client = AsyncWebClient(token=self._bot_token)
        post_kwargs: dict[str, Any] = {
            "channel": channel,
            "text": _escape_mrkdwn(message.text),
        }
        if message.blocks:
            post_kwargs["blocks"] = message.blocks
        if message.thread_ts:
            post_kwargs["thread_ts"] = message.thread_ts

        resp = await client.chat_postMessage(**post_kwargs)
        if resp["ok"]:
            receipt = MessageDeliveryReceipt(
                message_id=str(uuid.uuid4()),
                backend="slack_bot",
                channel="slack",
                provider_reference=resp.get("ts"),
            )
            logger.info(
                "slack.bot_sent",
                channel=channel,
                ts=resp.get("ts"),
                text_preview=message.text[:50],
            )
            return Ok(receipt)

        error_code = resp.get("error", "unknown")
        logger.warning("slack.bot_send_failed", channel=channel, error=error_code)
        return Err(
            SlackNotificationError(
                f"Slack bot API error: {error_code}",
                slack_error=error_code,
            )
        )

    async def _health_bot(self, timeout: float) -> HealthCheckResult:
        """Health check via Slack ``auth.test`` API."""
        try:
            from slack_sdk.web.async_client import (
                AsyncWebClient,
            )
        except ImportError:
            return HealthCheckResult(
                component="slack_bot",
                status=HealthStatus.UNHEALTHY,
                message="slack-sdk is not installed",
            )

        try:
            client = AsyncWebClient(token=self._bot_token, timeout=timeout)
            resp = await client.auth_test()
            if resp["ok"]:
                return HealthCheckResult(
                    component="slack_bot",
                    status=HealthStatus.HEALTHY,
                    details={"team": resp.get("team"), "bot_id": resp.get("bot_id")},
                )
            return HealthCheckResult(
                component="slack_bot",
                status=HealthStatus.UNHEALTHY,
                message=f"auth.test failed: {resp.get('error')}",
            )
        except Exception as exc:  # noqa: BLE001 — health check must never raise
            return HealthCheckResult(
                component="slack_bot",
                status=HealthStatus.UNHEALTHY,
                details={"error": str(exc)},
            )


__all__ = [
    "SlackMessage",
    "SlackNotificationError",
    "SlackNotifier",
]
