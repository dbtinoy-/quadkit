"""Fake distributed tracing implementation for testing."""

from __future__ import annotations

import secrets
from typing import Any, Self

__all__ = ["FakeSpan", "FakeTracer"]


class FakeSpan:
    """Minimal fake span for testing distributed tracing.

    Attributes:
        name: The span operation name.
        context: Opaque context object (trace_id, span_id pair).
        parent_context: Parent context if this span is linked to another trace.
        attributes: Span attributes dictionary.
        events: List of span events.
        status: Current span status.
    """

    def __init__(
        self,
        name: str,
        context: tuple[str, str],
        parent_context: tuple[str, str] | None = None,
    ) -> None:
        self.name = name
        self.context = context
        self.parent_context = parent_context
        self.attributes: dict[str, Any] = {}
        self.events: list[tuple[str, dict[str, Any]]] = []
        self.status: str = "ok"

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute."""
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add an event to the span."""
        self.events.append((name, attributes or {}))

    def record_exception(self, exception: Exception) -> None:
        """Record an exception on the span."""
        self.add_event(
            "exception",
            {
                "exception.type": type(exception).__name__,
                "exception.message": str(exception),
            },
        )

    def set_status(self, status: str) -> None:
        """Set the span status."""
        self.status = status

    def __enter__(self) -> Self:
        """Support usage as a context manager."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit context manager, recording any exception."""
        if exc_val is not None:
            self.record_exception(exc_val)  # type: ignore[arg-type]
            self.set_status("error")


class FakeTracer:
    """Minimal fake tracer implementing TracerProtocol.

    Generates W3C traceparent headers and tracks created spans for test inspection.

    Attributes:
        spans: List of all spans created by this tracer (for test inspection).
    """

    def __init__(self) -> None:
        self.spans: list[FakeSpan] = []
        self._current_span: FakeSpan | None = None

    def start_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        context: tuple[str, str] | None = None,
    ) -> FakeSpan:
        """Start a new span with optional parent context.

        Args:
            name: Span name.
            attributes: Optional span attributes.
            context: Optional parent context (trace_id, span_id). If provided,
                     this span continues the same trace with a new span_id.

        Returns:
            New FakeSpan instance.
        """
        if context:
            # Continue the same trace with a new span_id
            parent_trace_id, _ = context
            span_id = secrets.token_hex(8)
            span = FakeSpan(name, (parent_trace_id, span_id), parent_context=context)
        else:
            # Start a new trace
            trace_id = secrets.token_hex(16)
            span_id = secrets.token_hex(8)
            span = FakeSpan(name, (trace_id, span_id))

        if attributes:
            span.attributes.update(attributes)
        self.spans.append(span)
        self._current_span = span
        return span

    def get_current_span(self) -> FakeSpan | None:
        """Get the currently active span."""
        return self._current_span

    def inject_context(
        self, carrier: dict[str, str], context: tuple[str, str] | None = None
    ) -> None:
        """Inject trace context into a carrier dict (W3C traceparent format).

        Args:
            carrier: Mutable dict that will receive the trace headers.
            context: Optional context tuple (trace_id, span_id). If None, uses current span.
        """
        if context is None:
            if self._current_span is None:
                return
            context = self._current_span.context

        trace_id, span_id = context
        # W3C traceparent format: version-traceid-spanid-flags
        carrier["traceparent"] = f"00-{trace_id}-{span_id}-01"

    def extract_context(self, carrier: dict[str, str]) -> tuple[str, str] | None:
        """Extract trace context from a carrier dict (W3C traceparent).

        Args:
            carrier: Dict containing trace headers.

        Returns:
            Context tuple (trace_id, span_id) or None if no valid context found.
        """
        traceparent = carrier.get("traceparent")
        if not traceparent:
            return None

        parts = traceparent.split("-")
        if len(parts) != 4 or parts[0] != "00":
            return None

        return (parts[1], parts[2])
