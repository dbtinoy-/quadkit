"""Slack alert channel — respects business hours, queues outside."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.web.http_protocols import HTTPClientProtocol

logger = get_logger(__name__)

__all__ = ["SlackBusinessHoursDispatcher"]


class SlackBusinessHoursDispatcher:
    """Dispatches alerts to Slack during business hours; queues outside.

    Args:
        webhook_url: Slack incoming webhook URL.
        timezone: IANA timezone string (e.g. ``"UTC"``, ``"America/New_York"``).
        business_hours: ``(start_hour, end_hour)`` tuple in 24h format.
            Defaults to ``(9, 18)`` (9 AM – 6 PM).
        http_client: :class:`~quadkit.contracts.web.http_protocols.HTTPClientProtocol`
            implementation for outbound HTTP calls.
    """

    def __init__(
        self,
        webhook_url: str,
        timezone: str = "UTC",
        business_hours: tuple[int, int] = (9, 18),
        http_client: HTTPClientProtocol | None = None,
    ) -> None:
        self._webhook_url = webhook_url
        self._timezone = timezone
        self._business_hours = business_hours
        self._http_client = http_client
        self._queue: list[dict[str, str]] = []

    async def send_alert(
        self,
        title: str,
        message: str,
        severity: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        text = f"[{severity.upper()}] {title}: {message}"
        if self._is_business_hours():
            await self._post_to_slack(text)
        else:
            self._queue.append({"text": text, "severity": severity})

    async def send_metric_alert(
        self,
        metric_name: str,
        current_value: float,
        threshold: float,
        context: dict[str, Any] | None = None,
    ) -> None:
        text = f"[METRIC] {metric_name} = {current_value} (threshold: {threshold})"
        if self._is_business_hours():
            await self._post_to_slack(text)
        else:
            self._queue.append({"text": text, "severity": "high"})

    def _is_business_hours(self) -> bool:
        tz = ZoneInfo(self._timezone) if self._timezone != "UTC" else UTC
        now = datetime.now(tz=tz)
        start, end = self._business_hours
        return start <= now.hour < end

    async def _post_to_slack(self, text: str) -> None:
        if self._http_client is None:
            logger.info("slack_alert_queued", text=text)
            return
        payload = {"text": text}
        await self._http_client.request(
            "POST",
            url=self._webhook_url,
            json=payload,
        )
        logger.info("slack_alert_sent", text=text)

    async def flush_queue(self) -> None:
        """Send all queued alerts. Called at the start of business hours."""
        for item in self._queue:
            await self._post_to_slack(item["text"])
        self._queue.clear()
