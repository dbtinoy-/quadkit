"""Factory functions for creating MonitorProvider instances.

Convenience constructors for the most common monitoring backend configurations.
Import through ``quadkit.monitor.di`` — the public API is re-exported there.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from quadkit.monitor.config import MonitorConfig
    from quadkit.monitor.di.provider import MonitorProvider


def create_opentelemetry_provider(
    service_name: str = "quadkit-app",
    endpoint: str | None = None,
) -> MonitorProvider:
    """Create a MonitorProvider backed by OpenTelemetry.

    Args:
        service_name: Logical service name reported to the OTel collector.
        endpoint: Optional OTLP exporter endpoint URL.

    Returns:
        MonitorProvider configured with :class:`~quadkit.monitor.OpenTelemetryBackend`.
    """
    from quadkit.monitor import OpenTelemetryBackend
    from quadkit.monitor.di.provider import MonitorProvider

    backend = OpenTelemetryBackend(service_name, endpoint)
    return MonitorProvider(backend)


def create_prometheus_provider(port: int = 8000) -> MonitorProvider:
    """Create a MonitorProvider backed by Prometheus.

    Args:
        port: Port on which the Prometheus HTTP metrics endpoint is exposed.

    Returns:
        MonitorProvider configured with :class:`~quadkit.monitor.PrometheusBackend`.
    """
    from quadkit.monitor import PrometheusBackend
    from quadkit.monitor.di.provider import MonitorProvider

    backend = PrometheusBackend(port)
    return MonitorProvider(backend)


def create_provider_from_config(
    config: MonitorConfig | dict[str, Any] | None,
) -> MonitorProvider:
    """Create a MonitorProvider from a ``MonitorConfig`` object or mapping.

    Selects the appropriate monitoring backend and, when available,
    wires an async ``MetricsExporter`` for tasks and background jobs.

    Args:
        config: A ``MonitorConfig`` instance, dict, or compatible mapping.
            A plain ``dict`` is coerced into ``MonitorConfig`` automatically.

    Returns:
        Fully configured MonitorProvider.

    Raises:
        ValueError: When *config* is ``None``.
    """
    from quadkit.monitor.config import BackendType
    from quadkit.monitor.config import MonitorConfig as _MonitorCfg
    from quadkit.monitor.di.provider import MonitorProvider

    if config is None:
        raise ValueError("Monitor provider config is required")

    # Accept mapping/dict or already-constructed pydantic model.
    candidate: Any = config
    if not isinstance(candidate, _MonitorCfg):
        try:
            if isinstance(candidate, dict):
                config = _MonitorCfg(**candidate)
            else:
                config = _MonitorCfg.model_validate(candidate)
        except (ValueError, TypeError):
            pass

    # Get backend_type robustly (support enum or string values).
    backend_type = getattr(config, "backend_type", None)
    if isinstance(backend_type, str):
        try:
            backend_type = BackendType(backend_type)
        except (ValueError, TypeError):
            backend_type = BackendType.MEMORY

    from quadkit.monitor.backends.registry import MonitorBackendRegistryManager

    registry = MonitorBackendRegistryManager.with_defaults()
    monitor_config: MonitorConfig = cast("MonitorConfig", config)
    backend = registry.create_backend(backend_type, monitor_config)

    exporter = None
    if backend_type == BackendType.PROMETHEUS:
        try:
            from quadkit.monitor.backends.exporters import PrometheusMetricsExporter

            exporter = PrometheusMetricsExporter()
        except (ImportError, RuntimeError, TypeError):
            exporter = None

    return MonitorProvider(backend, exporter, config)


__all__ = [
    "create_opentelemetry_provider",
    "create_prometheus_provider",
    "create_provider_from_config",
]
