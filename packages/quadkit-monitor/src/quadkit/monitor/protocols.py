"""Public protocol surface for ``quadkit.monitor``."""

from __future__ import annotations

from quadkit.contracts.observability.metrics import (
    AlertDispatcherProtocol,
    MetricProtocol,
    MetricsBackendProtocol,
    MetricsCollectorProtocol,
)
from quadkit.contracts.observability.tracing import TracerProtocol
from quadkit.contracts.observability.tracing import TracerProtocol as TraceProvider
from quadkit.monitor.types import HealthCheckerProtocol

__all__ = [
    "AlertDispatcherProtocol",
    "HealthCheckerProtocol",
    "MetricProtocol",
    "MetricsBackendProtocol",
    "MetricsCollectorProtocol",
    "TraceProvider",
    "TracerProtocol",
]
