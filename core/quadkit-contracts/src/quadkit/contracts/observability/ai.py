"""AI observability contracts."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from quadkit.contracts.exceptions import QuadkitError


# Observability Errors
class MonitoringError(QuadkitError):
    """Base error raised during AI observability monitoring."""

    _code: str = "QK_ERR_AI_007"


class MetricsCollectionError(MonitoringError):
    """Error raised during metrics collection."""

    _code: str = "QK_ERR_AI_003"


class TracingError(QuadkitError):
    """Error raised during tracing operations."""

    _code: str = "QK_ERR_AI_004"


@runtime_checkable
class ObservabilityProtocol(Protocol):
    """Protocol for AI-specific metrics and tracing."""

    async def record_generation(
        self,
        model: str,
        provider: str,
        tokens_prompt: int,
        tokens_completion: int,
        latency_ms: float,
        successful: bool,
    ) -> None:
        """Record a single LLM generation event."""
        ...

    async def start_trace(
        self, name: str, metadata: dict[str, Any] | None = None
    ) -> str:
        """Start a trace block, returning a trace ID."""
        ...

    async def end_trace(
        self, trace_id: str, metadata: dict[str, Any] | None = None
    ) -> None:
        """End a trace block."""
        ...


@runtime_checkable
class AITracerProtocol(Protocol):
    """Protocol for AI distributed tracing.

    Implementations wrap individual LLM/vector calls in named spans,
    allowing distributed trace propagation without coupling to a
    specific tracing backend (OpenTelemetry, Jaeger, etc.).
    """

    def trace_llm_call(
        self,
        provider: str,
        model: str,
        *,
        streaming: bool = False,
    ) -> Any:
        """Return a context manager that wraps an LLM call in a trace span.

        Args:
            provider: Provider name (e.g. ``"openai"``).
            model: Model identifier.
            streaming: Whether this is a streaming call.

        Returns:
            A synchronous context manager.
        """
        ...


@runtime_checkable
class AIMetricsProtocol(Protocol):
    """Protocol for AI metrics collection.

    Implementations record counters, histograms, and gauges for
    LLM/vector operations without coupling to a specific metrics
    backend (Prometheus, StatsD, etc.).
    """

    def record_completion(
        self,
        provider: str,
        model: str,
        tokens: int,
        cost: float,
    ) -> None:
        """Record a successful LLM completion.

        Args:
            provider: Provider name.
            model: Model identifier.
            tokens: Total tokens consumed.
            cost: Estimated dollar cost.
        """
        ...

    def record_error(self, provider: str, error_type: str) -> None:
        """Record an LLM or vector store error.

        Args:
            provider: Provider name.
            error_type: Short error category string.
        """
        ...


@runtime_checkable
class AIHealthMonitorProtocol(Protocol):
    """Protocol for AI health monitoring.

    Allows the DI container to resolve health status of AI sub-systems
    (LLM availability, vector store connectivity, etc.) through a
    stable interface.
    """

    async def check(self) -> Any:
        """Run health checks and return a ``HealthCheckResult``-like object.

        Returns:
            An object with at least a ``status`` attribute.
        """
        ...

    def register_check(self, name: str, check: Any) -> None:
        """Register a named health-check callable.

        Args:
            name: Unique check name.
            check: An async callable returning a health status.
        """
        ...


__all__ = [
    "AIHealthMonitorProtocol",
    "AIMetricsProtocol",
    "AITracerProtocol",
    "MetricsCollectionError",
    "MonitoringError",
    "ObservabilityProtocol",
    "TracingError",
]
