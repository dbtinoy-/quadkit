"""OTEL exporter registry for tracing and metrics."""

from __future__ import annotations

from typing import Any, Protocol


class TracingExporterHandler(Protocol):
    """Protocol for tracing exporter handlers."""

    def can_handle(self, exporter_type: str) -> bool:
        """Check if this handler can handle the exporter type."""
        ...

    def create_exporter(self, exp_config: Any) -> Any:
        """Create a tracing exporter instance."""
        ...


class ConsoleTracingExporterHandler:
    """Handler for console tracing exporter.

    Creates a ConsoleSpanExporter for outputting traces to the console.
    """

    def can_handle(self, exporter_type: str) -> bool:
        """Check if this handler can handle the exporter type.

        Args:
            exporter_type: The type of exporter to check.

        Returns:
            True if exporter_type is "console", False otherwise.
        """
        return exporter_type == "console"

    def create_exporter(self, exp_config: Any) -> Any:
        """Create a console tracing exporter instance.

        Args:
            exp_config: Configuration for the exporter (unused for console).

        Returns:
            A ConsoleSpanExporter instance.
        """
        from opentelemetry.sdk.trace.export import (
            ConsoleSpanExporter,
        )

        return ConsoleSpanExporter()


class OTLPTracingExporterHandler:
    """Handler for OTLP tracing exporter.

    Creates an OTLPSpanExporter for sending traces to an OTLP-compatible backend.
    """

    def can_handle(self, exporter_type: str) -> bool:
        """Check if this handler can handle the exporter type.

        Args:
            exporter_type: The type of exporter to check.

        Returns:
            True if exporter_type is "otlp", False otherwise.
        """
        return exporter_type == "otlp"

    def create_exporter(self, exp_config: Any) -> Any:
        """Create an OTLP tracing exporter instance.

        Args:
            exp_config: Configuration with endpoint and headers.

        Returns:
            An OTLPSpanExporter instance.
        """
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        return OTLPSpanExporter(
            endpoint=exp_config.endpoint,
            headers=exp_config.headers,
        )


class MetricsExporterHandler(Protocol):
    """Protocol for metrics exporter handlers."""

    def can_handle(self, exporter_type: str) -> bool:
        """Check if this handler can handle the exporter type."""
        ...

    def create_exporter(self, exp_config: Any) -> Any:
        """Create a metrics exporter instance."""
        ...


class ConsoleMetricsExporterHandler:
    """Handler for console metrics exporter.

    Creates a ConsoleMetricExporter for outputting metrics to the console.
    """

    def can_handle(self, exporter_type: str) -> bool:
        """Check if this handler can handle the exporter type.

        Args:
            exporter_type: The type of exporter to check.

        Returns:
            True if exporter_type is "console", False otherwise.
        """
        return exporter_type == "console"

    def create_exporter(self, exp_config: Any) -> Any:
        """Create a console metrics exporter instance.

        Args:
            exp_config: Configuration for the exporter (unused for console).

        Returns:
            A ConsoleMetricExporter instance.
        """
        from opentelemetry.sdk.metrics.export import (
            ConsoleMetricExporter,
        )

        return ConsoleMetricExporter()


class OTLPMetricsExporterHandler:
    """Handler for OTLP metrics exporter.

    Creates an OTLPMetricExporter for sending metrics to an OTLP-compatible backend.
    """

    def can_handle(self, exporter_type: str) -> bool:
        """Check if this handler can handle the exporter type.

        Args:
            exporter_type: The type of exporter to check.

        Returns:
            True if exporter_type is "otlp", False otherwise.
        """
        return exporter_type == "otlp"

    def create_exporter(self, exp_config: Any) -> Any:
        """Create an OTLP metrics exporter instance.

        Args:
            exp_config: Configuration with endpoint and headers.

        Returns:
            An OTLPMetricExporter instance.
        """
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )

        return OTLPMetricExporter(
            endpoint=exp_config.endpoint,
            headers=exp_config.headers,
        )


class TracingExporterRegistry:
    """Central registry for tracing exporters.

    Manages a collection of handlers for creating tracing exporters.
    Handlers are checked in order until one is found that can handle the exporter type.

    Example:
        >>> registry = TracingExporterRegistry()
        >>> registry.register(CustomTracingExporterHandler())
        >>> exporter = registry.create_exporter(config)
    """

    def __init__(self) -> None:
        """Initialize the registry without any handlers."""
        self._handlers: list[TracingExporterHandler] = []

    @classmethod
    def _default_entries(cls) -> dict[str, TracingExporterHandler]:
        """Declare the built-in tracing exporter handlers (console, OTLP)."""
        return {
            "console": ConsoleTracingExporterHandler(),
            "otlp": OTLPTracingExporterHandler(),
        }

    @classmethod
    def with_defaults(cls) -> TracingExporterRegistry:
        """Create a registry pre-populated with the built-in default handlers."""
        registry = cls()
        registry._handlers = list(cls._default_entries().values())
        return registry

    def register(self, handler: TracingExporterHandler) -> None:
        """Register a new tracing exporter handler.

        Args:
            handler: The handler to register; inserted at the head of the list.
        """
        self._handlers.insert(0, handler)

    def create_exporter(self, exp_config: Any) -> Any:
        """Create an exporter for the given config.

        Args:
            exp_config: Configuration object with a 'type' attribute.

        Returns:
            An exporter instance, or None if no handler can handle the type.
        """
        for handler in self._handlers:
            if handler.can_handle(exp_config.type):
                return handler.create_exporter(exp_config)
        return None


class MetricsExporterRegistry:
    """Central registry for metrics exporters.

    Manages a collection of handlers for creating metrics exporters.
    Handlers are checked in order until one is found that can handle the exporter type.

    Example:
        >>> registry = MetricsExporterRegistry()
        >>> registry.register(CustomMetricsExporterHandler())
        >>> exporter = registry.create_exporter(config)
    """

    def __init__(self) -> None:
        """Initialize the registry without any handlers."""
        self._handlers: list[MetricsExporterHandler] = []

    @classmethod
    def _default_entries(cls) -> dict[str, MetricsExporterHandler]:
        """Declare the built-in metrics exporter handlers (console, OTLP)."""
        return {
            "console": ConsoleMetricsExporterHandler(),
            "otlp": OTLPMetricsExporterHandler(),
        }

    @classmethod
    def with_defaults(cls) -> MetricsExporterRegistry:
        """Create a registry pre-populated with the built-in default handlers."""
        registry = cls()
        registry._handlers = list(cls._default_entries().values())
        return registry

    def register(self, handler: MetricsExporterHandler) -> None:
        """Register a new metrics exporter handler.

        Args:
            handler: The handler to register; inserted at the head of the list.
        """
        self._handlers.insert(0, handler)

    def create_exporter(self, exp_config: Any) -> Any:
        """Create an exporter for the given config.

        Args:
            exp_config: Configuration object with a 'type' attribute.

        Returns:
            An exporter instance, or None if no handler can handle the type.
        """
        for handler in self._handlers:
            if handler.can_handle(exp_config.type):
                return handler.create_exporter(exp_config)
        return None
