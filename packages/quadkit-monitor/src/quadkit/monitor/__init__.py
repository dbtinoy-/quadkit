"""Quadkit Monitor Package - Observability and monitoring"""

from __future__ import annotations

import importlib.metadata

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from typing import TYPE_CHECKING, Any

from quadkit.monitor.constants import __version__ as __version__

if TYPE_CHECKING:
    from quadkit.contracts.observability.metrics import (
        AlertDispatcherProtocol,
        MetricProtocol,
        MetricsBackendProtocol,
    )
    from quadkit.contracts.observability.tracing import TracerProtocol
    from quadkit.logging import (
        Logger,
        configure_logging,
        get_logger,
    )
    from quadkit.monitor.alerts import LoggingAlertDispatcher
    from quadkit.monitor.backends import (
        OpenTelemetryBackend,
        PrometheusBackend,
    )
    from quadkit.monitor.backends.exporters import PrometheusMetricsExporter
    from quadkit.monitor.backends.exporters.otel_registry import (
        ConsoleMetricsExporterHandler,
        ConsoleTracingExporterHandler,
        MetricsExporterRegistry,
        OTLPMetricsExporterHandler,
        OTLPTracingExporterHandler,
        TracingExporterRegistry,
    )
    from quadkit.monitor.config import (
        BackendType,
        ErrorTrackingConfig,
        HealthCheckConfig,
        MetricsConfig,
        MonitorConfig,
        OpenTelemetryConfig,
        PrometheusConfig,
        SamplerType,
        TracingConfig,
    )
    from quadkit.monitor.decorators import monitor
    from quadkit.monitor.di.factories import (
        create_opentelemetry_provider,
        create_prometheus_provider,
        create_provider_from_config,
    )
    from quadkit.monitor.di.provider import (
        MonitorProvider,
    )
    from quadkit.monitor.di.sub_providers.observability import ObservabilityProvider
    from quadkit.monitor.error_tracking import (
        ErrorTrackerProtocol,
        NullErrorTracker,
        SentryErrorTracker,
        setup_error_tracking,
    )
    from quadkit.monitor.exceptions import (
        BackendNotAvailableError,
        InvalidMetricError,
        MetricNotFoundError,
        MonitorError,
        SpanError,
    )
    from quadkit.monitor.health import (
        FunctionHealthCheck,
        HealthCheck,
        HealthCheckCategory,
        HealthChecker,
        HealthCheckerRegistry,
        HealthCheckRegistry,
        HealthCheckResult,
        HealthStatus,
        health_checker,
    )
    from quadkit.monitor.instrumentation.database import instrument_database
    from quadkit.monitor.instrumentation.decorators import (
        metered,
        traced,
    )
    from quadkit.monitor.instrumentation.http import OTelMiddleware
    from quadkit.monitor.instrumentation.messaging import (
        inject_trace_context,
        trace_consume,
        trace_publish,
    )
    from quadkit.monitor.metrics import (
        BufferedMetricEntry,
        BufferedMetricRecorder,
        Counter,
        Gauge,
        Histogram,
        MetricsCollectorProtocol,
        Summary,
    )
    from quadkit.monitor.middleware import (
        HealthCheckProvider,
        PrometheusMiddleware,
    )
    from quadkit.monitor.profiling import (
        FunctionProfileResult,
        PerformanceMetrics,
        PerformanceMonitor,
        PerformanceMonitorConfig,
        PerformanceMonitorError,
        PerformanceMonitorState,
        PerformanceSnapshot,
        get_performance_summary,
        monitor_async_operation,
        profile_async_function,
    )
    from quadkit.monitor.services.core import (
        MetricProxy,
        ObservabilityService,
    )
    from quadkit.monitor.slo.monitor import SLOMonitor
    from quadkit.monitor.slo.objective import (
        SLO,
        SLOViolation,
    )
    from quadkit.monitor.tracing import (
        ConsoleSpanExporter,
        InMemoryTraceProvider,
        Span,
        SpanContext,
        SpanExporter,
        SpanKind,
        SpanStatus,
        Tracer,
    )
    from quadkit.monitor.types import HealthCheckerProtocol, MetricValue
    from quadkit.observability.core import (
        NoOpHealthCheckRegistry,
        NoOpMetricsCollector,
        NoOpSpan,
        NoOpTracer,
    )


_LAZY_IMPORTS = {
    # Module
    "MonitorModule": "quadkit.monitor.module",
    # Config
    "BackendType": "quadkit.monitor.config",
    "SamplerType": "quadkit.monitor.config",
    "MetricsConfig": "quadkit.monitor.config",
    "TracingConfig": "quadkit.monitor.config",
    "HealthCheckConfig": "quadkit.monitor.config",
    "OpenTelemetryConfig": "quadkit.monitor.config",
    "PrometheusConfig": "quadkit.monitor.config",
    "MonitorConfig": "quadkit.monitor.config",
    "ErrorTrackingConfig": "quadkit.monitor.config",
    # Error tracking
    "ErrorTrackerProtocol": "quadkit.monitor.error_tracking",
    "NullErrorTracker": "quadkit.monitor.error_tracking",
    "SentryErrorTracker": "quadkit.monitor.error_tracking",
    "setup_error_tracking": "quadkit.monitor.error_tracking",
    # Protocols
    "MetricProtocol": "quadkit.contracts.observability",
    "MetricsBackendProtocol": "quadkit.contracts.observability",
    "AlertDispatcherProtocol": "quadkit.contracts.observability",
    # Types
    "MetricValue": "quadkit.monitor.types",
    "HealthCheckerProtocol": "quadkit.monitor.types",
    "SpanKind": "quadkit.monitor.tracing",
    "SpanStatus": "quadkit.monitor.tracing",
    # Exceptions
    "MonitorError": "quadkit.monitor.exceptions",
    "BackendNotAvailableError": "quadkit.monitor.exceptions",
    "MetricNotFoundError": "quadkit.monitor.exceptions",
    "InvalidMetricError": "quadkit.monitor.exceptions",
    "SpanError": "quadkit.monitor.exceptions",
    # Metrics
    "MetricsCollectorProtocol": "quadkit.monitor.metrics",
    "Counter": "quadkit.monitor.metrics",
    "Gauge": "quadkit.monitor.metrics",
    "Histogram": "quadkit.monitor.metrics",
    "Summary": "quadkit.monitor.metrics",
    "BufferedMetricEntry": "quadkit.monitor.metrics",
    "BufferedMetricRecorder": "quadkit.monitor.metrics",
    # Tracing
    "Tracer": "quadkit.monitor.tracing",
    "Span": "quadkit.monitor.tracing",
    "SpanContext": "quadkit.monitor.tracing",
    "SpanExporter": "quadkit.monitor.tracing",
    "ConsoleSpanExporter": "quadkit.monitor.tracing",
    "InMemoryTraceProvider": "quadkit.monitor.tracing",
    # Logging
    "Logger": "quadkit.logging",
    "get_logger": "quadkit.logging",
    "configure_logging": "quadkit.logging",
    # Backends
    "OpenTelemetryBackend": "quadkit.monitor.backends",
    "PrometheusBackend": "quadkit.monitor.backends",
    # Middleware
    "PrometheusMiddleware": "quadkit.monitor.middleware",
    "HealthCheckProvider": "quadkit.monitor.middleware",
    # Health
    "HealthStatus": "quadkit.monitor.health",
    "HealthCheck": "quadkit.monitor.health",
    "HealthCheckCategory": "quadkit.monitor.health",
    "HealthCheckResult": "quadkit.monitor.health",
    "HealthCheckRegistry": "quadkit.monitor.health",
    "HealthChecker": "quadkit.monitor.health",
    "HealthCheckerRegistry": "quadkit.monitor.health",
    "FunctionHealthCheck": "quadkit.monitor.health",
    "health_checker": "quadkit.monitor.health",
    # NoOp stubs
    "NoOpSpan": "quadkit.observability.core",
    "NoOpTracer": "quadkit.observability.core",
    "NoOpMetricsCollector": "quadkit.observability.core",
    "NoOpHealthCheckRegistry": "quadkit.observability.core",
    # Observability service
    "ObservabilityService": "quadkit.monitor.services.core",
    "MetricProxy": "quadkit.monitor.services.core",
    # Decorators
    "metered": "quadkit.monitor.instrumentation.decorators",
    "traced": "quadkit.monitor.instrumentation.decorators",
    "monitor": "quadkit.monitor.decorators",
    # Provider
    "ObservabilityProvider": "quadkit.monitor.di.sub_providers.observability",
    "MonitorProvider": "quadkit.monitor.di.provider",
    "create_opentelemetry_provider": "quadkit.monitor.di.factories",
    "create_prometheus_provider": "quadkit.monitor.di.factories",
    "create_provider_from_config": "quadkit.monitor.di.factories",
    "PrometheusMetricsExporter": "quadkit.monitor.backends.exporters",
    "ConsoleTracingExporterHandler": "quadkit.monitor.backends.exporters.otel_registry",
    "OTLPTracingExporterHandler": "quadkit.monitor.backends.exporters.otel_registry",
    "ConsoleMetricsExporterHandler": "quadkit.monitor.backends.exporters.otel_registry",
    "OTLPMetricsExporterHandler": "quadkit.monitor.backends.exporters.otel_registry",
    "TracingExporterRegistry": "quadkit.monitor.backends.exporters.otel_registry",
    "MetricsExporterRegistry": "quadkit.monitor.backends.exporters.otel_registry",
    # Instrumentation
    "instrument_database": "quadkit.monitor.instrumentation.database",
    "OTelMiddleware": "quadkit.monitor.instrumentation.http",
    "trace_publish": "quadkit.monitor.instrumentation.messaging",
    "trace_consume": "quadkit.monitor.instrumentation.messaging",
    "inject_trace_context": "quadkit.monitor.instrumentation.messaging",
    # Profiling
    "PerformanceMonitor": "quadkit.monitor.profiling",
    "PerformanceMonitorConfig": "quadkit.monitor.profiling",
    "PerformanceMonitorError": "quadkit.monitor.profiling",
    "PerformanceMonitorState": "quadkit.monitor.profiling",
    "PerformanceMetrics": "quadkit.monitor.profiling",
    "PerformanceSnapshot": "quadkit.monitor.profiling",
    "FunctionProfileResult": "quadkit.monitor.profiling",
    "get_performance_summary": "quadkit.monitor.profiling",
    "monitor_async_operation": "quadkit.monitor.profiling",
    "profile_async_function": "quadkit.monitor.profiling",
    # SLO
    "SLO": "quadkit.monitor.slo.objective",
    "SLOViolation": "quadkit.monitor.slo.objective",
    "SLOMonitor": "quadkit.monitor.slo.monitor",
    # Alerts
    "LoggingAlertDispatcher": "quadkit.monitor.alerts",
    # Hooks
    "AlertFiredHook": "quadkit.monitor.hooks",
    "HealthCheckRunHook": "quadkit.monitor.hooks",
    "MetricRecordedHook": "quadkit.monitor.hooks",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        import importlib

        module_path = _LAZY_IMPORTS[name]
        module = importlib.import_module(module_path)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__} has no attribute {name}")


def __dir__() -> list[str]:
    return [*list(_LAZY_IMPORTS.keys()), "__version__"]


__all__ = list(_LAZY_IMPORTS.keys())
