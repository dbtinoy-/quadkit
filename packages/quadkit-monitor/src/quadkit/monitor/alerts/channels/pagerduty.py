"""PagerDuty alert channel — PagerDuty Events API v2."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.web.http_protocols import HTTPClientProtocol

logger = get_logger(__name__)

__all__ = ["PagerDutyAlertDispatcher"]

_PAGERDUTY_EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"

_SEVERITY_MAP: dict[str, str] = {
    "low": "info",
    "medium": "warning",
    "high": "error",
    "critical": "critical",
}


def _dedup_key(title: str) -> str:
    """Derive a stable Events API v2 ``dedup_key`` from the alert title.

    PagerDuty correlates trigger events sharing a ``dedup_key`` into one
    incident, so recurring alerts of the same type (e.g. repeated
    "Metric breach: http.request.duration") update the existing incident
    instead of opening a new one per event.
    """
    digest = hashlib.sha256(f"quadkit-monitor:{title}".encode()).hexdigest()
    return f"quadkit-{digest[:24]}"


class PagerDutyAlertDispatcher:
    """Dispatches alerts to PagerDuty via the Events API v2.

    Args:
        integration_key: PagerDuty Events API v2 integration key.
        http_client: :class:`~quadkit.contracts.web.http_protocols.HTTPClientProtocol`
            implementation for outbound HTTP calls.
    """

    def __init__(
        self,
        integration_key: str,
        http_client: HTTPClientProtocol,
    ) -> None:
        self._integration_key = integration_key
        self._http_client = http_client

    async def send_alert(
        self,
        title: str,
        message: str,
        severity: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        payload = self._build_payload(title, message, severity, context)
        await self._post(payload)

    async def send_metric_alert(
        self,
        metric_name: str,
        current_value: float,
        threshold: float,
        context: dict[str, Any] | None = None,
    ) -> None:
        severity = (context or {}).get("severity", "critical")
        title = f"Metric breach: {metric_name}"
        message = f"{metric_name} = {current_value} (threshold: {threshold})"
        payload = self._build_payload(title, message, severity, context)
        await self._post(payload)

    def _build_payload(
        self,
        title: str,
        message: str,
        severity: str,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        pd_severity = _SEVERITY_MAP.get(severity, "info")
        ctx = context or {}
        return {
            "routing_key": self._integration_key,
            "event_action": "trigger",
            "payload": {
                "summary": f"{title}: {message}",
                "severity": pd_severity,
                "source": "quadkit-monitor",
                # Stable per logical alert type: recurrences correlate to
                # the same incident (heartbeat) instead of opening new ones.
                "dedup_key": _dedup_key(title),
                "custom_details": ctx,
            },
        }

    async def _post(self, payload: dict[str, Any]) -> None:
        resp = await self._http_client.request(
            "POST",
            url=_PAGERDUTY_EVENTS_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        status = resp.status if hasattr(resp, "status") else 0
        if status >= 400:
            logger.error(
                "pagerduty_alert_failed",
                status=status,
                payload_summary=payload.get("payload", {}).get("summary"),
            )
            msg = f"PagerDuty API returned status {status}"
            raise ConnectionError(msg)

        logger.info(
            "pagerduty_alert_sent",
            status=status,
            payload_summary=payload.get("payload", {}).get("summary"),
        )
