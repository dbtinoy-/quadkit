"""Observability contracts — tracing, metrics, audit, and AI observability."""

from __future__ import annotations

from quadkit.contracts.observability.ai import (
    AIHealthMonitorProtocol,
    AIMetricsProtocol,
    AITracerProtocol,
    MetricsCollectionError,
    ObservabilityProtocol,
    TracingError,
)
from quadkit.contracts.observability.audit import AuditVerifierSchedulerProtocol
from quadkit.contracts.observability.metrics import (
    AlertDispatcherProtocol,
    HealthCheckRegistryProtocol,
    MetricProtocol,
    MetricsBackendProtocol,
    MetricsCollectorProtocol,
    MetricsFactoryProtocol,
    MetricsRecorderProtocol,
)
from quadkit.contracts.observability.tracing import SpanProtocol, TracerProtocol

__all__ = [
    "AIHealthMonitorProtocol",
    "AIMetricsProtocol",
    "AITracerProtocol",
    "AlertDispatcherProtocol",
    "AuditVerifierSchedulerProtocol",
    "HealthCheckRegistryProtocol",
    "MetricProtocol",
    "MetricsBackendProtocol",
    "MetricsCollectionError",
    "MetricsCollectorProtocol",
    "MetricsFactoryProtocol",
    "MetricsRecorderProtocol",
    "ObservabilityProtocol",
    "SpanProtocol",
    "TracerProtocol",
    "TracingError",
]
