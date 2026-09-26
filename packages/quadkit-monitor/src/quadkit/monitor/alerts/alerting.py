"""Logging-backed implementation of :class:`AlertDispatcherProtocol`.

Dispatches alerts to the structured logger at severity-appropriate log
levels.  Suitable for development environments or as a safe default when
no external notification channel is configured.

Severity mapping:

+--------------+------------+
| severity     | log level  |
+==============+============+
| ``low``      | WARNING    |
| ``medium``   | WARNING    |
| ``high``     | ERROR      |
| ``critical`` | ERROR      |
| *(other)*    | WARNING    |
+--------------+------------+

Example::

    from quadkit.monitor.alerts import LoggingAlertDispatcher

    dispatcher = LoggingAlertDispatcher()
    await dispatcher.send_alert(
        title="Disk space low",
        message="Available disk space is below 10 %.",
        severity="high",
        context={"host": "web-01", "available_gb": 4.2},
    )
"""

from __future__ import annotations

from typing import Any

from quadkit.logging import get_logger

logger = get_logger(__name__)

_HIGH_SEVERITY_LEVELS = frozenset({"high", "critical"})


class LoggingAlertDispatcher:
    """Dispatches alerts to the structured logger.

    Implements :class:`~quadkit.contracts.observability.protocols.AlertDispatcherProtocol`.

    Low and medium-severity alerts are logged at ``WARNING`` level;
    high and critical alerts are logged at ``ERROR`` level.

    This implementation is always available with no external dependencies
    and is registered by :class:`~quadkit.monitor.di.provider.MonitorProvider`
    as the default
    :class:`~quadkit.contracts.observability.protocols.AlertDispatcherProtocol`
    binding when no other dispatcher is configured.
    """

    async def send_alert(
        self,
        title: str,
        message: str,
        severity: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Dispatch a free-form operational alert to the structured logger.

        Args:
            title: Short, human-readable alert title.
            message: Detailed alert message.
            severity: Severity level string, e.g. ``"low"``, ``"high"``,
                ``"critical"``.
            context: Optional free-form mapping of additional metadata
                included as structured key-value pairs on the log record.
        """
        extra: dict[str, Any] = {
            "alert_title": title,
            "alert_severity": severity,
            "alert_message": message,
        }
        if context:
            extra["alert_context"] = context

        if severity.lower() in _HIGH_SEVERITY_LEVELS:
            logger.error("alert_dispatched", **extra)
        else:
            logger.warning("alert_dispatched", **extra)

    async def send_metric_alert(
        self,
        metric_name: str,
        current_value: float,
        threshold: float,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Dispatch a metric-threshold alert to the structured logger.

        The alert is always logged at ``WARNING`` level unless the breach
        exceeds the threshold by more than 100 %, in which case ``ERROR``
        is used.

        Args:
            metric_name: Name of the metric that breached its threshold.
            current_value: Observed metric value at the time of the alert.
            threshold: The configured threshold that was exceeded.
            context: Optional free-form mapping of additional metadata.
        """
        extra: dict[str, Any] = {
            "metric_name": metric_name,
            "current_value": current_value,
            "threshold": threshold,
        }
        if context:
            extra["alert_context"] = context

        # Escalate to ERROR when the breach is severe (>2x the threshold).
        if threshold != 0 and current_value >= threshold * 2:
            logger.error("metric_alert_dispatched", **extra)
        else:
            logger.warning("metric_alert_dispatched", **extra)


__all__ = ["LoggingAlertDispatcher"]
