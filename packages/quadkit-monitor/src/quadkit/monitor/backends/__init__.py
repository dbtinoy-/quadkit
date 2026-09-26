"""Backend implementations module.

This module provides various monitoring backend implementations
including OpenTelemetry and Prometheus.
"""

from __future__ import annotations

from quadkit.monitor.backends.opentelemetry import OpenTelemetryBackend
from quadkit.monitor.backends.prometheus import PrometheusBackend

__all__ = [
    "OpenTelemetryBackend",
    "PrometheusBackend",
]
