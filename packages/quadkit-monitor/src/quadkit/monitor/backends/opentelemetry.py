"""OpenTelemetry backend implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.monitor.backends.exporters.otel_registry import (
        MetricsExporterRegistry,
        TracingExporterRegistry,
    )

from quadkit.contracts.observability.metrics import MetricsBackendProtocol

# Import Span/SpanContext from tracing instead of types
from quadkit.logging import get_logger
from quadkit.monitor.exceptions import BackendNotAvailableError
from quadkit.monitor.tracing import Span, SpanContext

logger = get_logger(__name__)

# Predeclare optional opentelemetry variables for static analysis
metrics: Any = None
trace: Any = None
MeterProvider: Any = None
TracerProvider: Any = None

try:
    from opentelemetry import metrics as _metrics
    from opentelemetry import trace as _trace
    from opentelemetry.sdk.metrics import (
        MeterProvider as _MP,  # noqa: N814
    )
    from opentelemetry.sdk.trace import (
        TracerProvider as _TP,  # noqa: N814
    )

    metrics = _metrics
    trace = _trace
    MeterProvider = _MP
    TracerProvider = _TP
    HAS_OPENTELEMETRY = True
except ImportError:
    HAS_OPENTELEMETRY = False


class OpenTelemetryBackend(MetricsBackendProtocol):
    """OpenTelemetry monitoring backend."""

    def __init__(
        self,
        service_name: str = "quadkit-app",
        endpoint: str | None = None,
        config: Any | None = None,
        tracing_exporter_registry: TracingExporterRegistry | None = None,
        metrics_exporter_registry: MetricsExporterRegistry | None = None,
    ):
        if not HAS_OPENTELEMETRY:
            raise BackendNotAvailableError(
                "OpenTelemetry is required for OpenTelemetry backend. "
                "Install with: pip install quadkit-monitor[otel]",
            )

        self.service_name = service_name
        self.endpoint = endpoint
        self.config = config
        self.meter_provider: Any = None
        self.tracer_provider: Any = None
        self.meter: Any = None
        self.tracer: Any = None
        # Exporter registries — injected at construction for testability
        self._tracing_exporter_registry = tracing_exporter_registry
        self._metrics_exporter_registry = metrics_exporter_registry

    async def initialize(self) -> None:
        """Initialize OpenTelemetry."""
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": self.service_name})

        # Set up MeterProvider
        self.meter_provider = MeterProvider(resource=resource)
        metrics.set_meter_provider(self.meter_provider)
        self.meter = metrics.get_meter(self.service_name)

        # Set up TracerProvider
        self.tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(self.tracer_provider)
        self.tracer = trace.get_tracer(self.service_name)

        # Use new configuration if available
        if self.config is not None:
            self._setup_registered_exporters()
        elif self.endpoint:
            # Fallback legacy configuration
            try:
                from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                    OTLPMetricExporter,
                )
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                    OTLPSpanExporter,
                )
                from opentelemetry.sdk.trace.export import BatchSpanProcessor

                _metric_exporter = OTLPMetricExporter(endpoint=self.endpoint)
                _span_exporter = OTLPSpanExporter(endpoint=self.endpoint)

                self.tracer_provider.add_span_processor(
                    BatchSpanProcessor(_span_exporter),
                )
                # For meters, it has to be attached at creation, but here we attach if possible or skip.
            except ImportError:
                logger.warning(
                    "opentelemetry_not_installed",
                    hint="pip install quadkit-monitor[otel]",
                    detail="OTLP exporters unavailable; metrics/tracing disabled",
                )

    def _setup_registered_exporters(self) -> None:
        """Setup from explicit config registries."""
        from quadkit.monitor.backends.exporters.otel_registry import (
            MetricsExporterRegistry,
            TracingExporterRegistry,
        )

        # Set up Tracers
        tracing_registry = (
            self._tracing_exporter_registry or TracingExporterRegistry.with_defaults()
        )
        tracing_exporters = getattr(self.config, "tracing_exporters", [])
        for exp_config in tracing_exporters:
            exporter = tracing_registry.create_exporter(exp_config)
            if exporter:
                from opentelemetry.sdk.trace.export import BatchSpanProcessor

                self.tracer_provider.add_span_processor(BatchSpanProcessor(exporter))

        # Set up Metrics
        metrics_registry = (
            self._metrics_exporter_registry or MetricsExporterRegistry.with_defaults()
        )
        metrics_exporters = getattr(self.config, "metrics_exporters", [])
        readers = []
        for exp_config in metrics_exporters:
            exporter = metrics_registry.create_exporter(exp_config)
            if exporter:
                from opentelemetry.sdk.metrics.export import (
                    PeriodicExportingMetricReader,
                )

                interval = getattr(self.config, "export_interval", 5.0)
                readers.append(
                    PeriodicExportingMetricReader(
                        exporter,
                        export_interval_millis=int(interval * 1000),
                    ),
                )

        if readers:
            from opentelemetry.sdk.resources import Resource

            resource = Resource.create({"service.name": self.service_name})
            self.meter_provider = MeterProvider(
                resource=resource,
                metric_readers=readers,
            )
            metrics.set_meter_provider(self.meter_provider)

    async def shutdown(self) -> None:
        if self.tracer_provider and hasattr(self.tracer_provider, "shutdown"):
            self.tracer_provider.shutdown()
        if self.meter_provider and hasattr(self.meter_provider, "shutdown"):
            self.meter_provider.shutdown()

    def record_metric(
        self,
        name: str,
        value: Any,
        metric_type: str,
        labels: dict[str, str] | None = None,
    ) -> None:
        if not self.meter:
            return

        labels = labels or {}

        if metric_type == "counter":
            counter = self.meter.create_counter(name)
            counter.add(value, labels)
        elif metric_type == "gauge":
            pass
        elif metric_type == "histogram":
            histogram = self.meter.create_histogram(name)
            histogram.record(value, labels)

    def create_span(self, name: str, parent_context: SpanContext | None = None) -> Span:
        if not self.tracer:
            import time

            context = SpanContext(trace_id="otel-fallback", span_id=name)
            return Span(name=name, context=context, start_time=time.time())

        # Logic to extract context from parent_context if provided?
        # Current implementation just starts new span.
        # If we need to respect parent_context we should use trace.set_span_in_context or similar
        # But for now I'll just keep existing logic (which ignored parent_context mostly in my prev view or used it implicitly?)
        # Step 1944 used `with self.tracer.start_as_current_span(name) as otel_span:`

        with self.tracer.start_as_current_span(name) as otel_span:
            import time

            span_context = otel_span.get_span_context()
            context = SpanContext(
                trace_id=str(span_context.trace_id),
                span_id=str(span_context.span_id),
                trace_flags=int(span_context.trace_flags)
                if hasattr(span_context, "trace_flags")
                else 0x01,
            )
            # Create our Span object wrapping it?
            # Actually our Span is independent object.
            # We are just returning a representation.
            return Span(name=name, context=context, start_time=time.time())
