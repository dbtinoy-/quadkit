"""Root hook payload surface for quadkit-monitor.

Defines canonical payload dataclasses for observability/monitoring hook points.
Actual hook registration and invocation use the framework's string-keyed
``HookRegistryProtocol`` action/filter APIs.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "AlertFiredHook",
    "HealthCheckRunHook",
    "MetricRecordedHook",
]


@dataclass(frozen=True, kw_only=True)
class MetricRecordedHook:
    """Payload fired when a metric data point is recorded.

    Attributes:
        metric_name: Name of the metric being recorded.
        value: Numeric value of the data point.
    """

    metric_name: str
    value: float


@dataclass(frozen=True, kw_only=True)
class AlertFiredHook:
    """Payload fired when a monitoring alert is triggered.

    Attributes:
        alert_name: Name of the alert rule that fired.
        severity: Severity level (e.g. ``"warning"``, ``"critical"``).
    """

    alert_name: str
    severity: str


@dataclass(frozen=True, kw_only=True)
class HealthCheckRunHook:
    """Payload fired after a health check probe completes.

    Attributes:
        check_name: Name of the health check that ran.
        healthy: ``True`` if the check passed.
    """

    check_name: str
    healthy: bool
