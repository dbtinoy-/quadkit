"""Framework integration for quadkit-monitor."""

from __future__ import annotations

from quadkit.monitor.di.factories import (
    create_opentelemetry_provider,
    create_prometheus_provider,
    create_provider_from_config,
)
from quadkit.monitor.di.provider import MonitorProvider
from quadkit.monitor.di.sub_providers.observability import ObservabilityProvider

__all__ = [
    "MonitorProvider",
    "ObservabilityProvider",
    "create_opentelemetry_provider",
    "create_prometheus_provider",
    "create_provider_from_config",
]
