"""Metrics exporter adapters for monitoring backends.

Provides a Prometheus-compatible MetricsExporter implementation that adapts
prometheus_client primitives to the async MetricsExporter protocol used by
other framework components (e.g., scheduled tasks).

The MetricsExporter protocol is defined in quadkit-ent and registered via
the container. This package exposes the concrete implementation on demand.
"""

from __future__ import annotations

from quadkit.monitor.backends.exporters.prometheus import (
    HAS_PROMETHEUS,
    PrometheusMetricsExporter,
)

__all__ = ["HAS_PROMETHEUS", "PrometheusMetricsExporter"]
