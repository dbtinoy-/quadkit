"""OpenTelemetry protocols for distributed tracing.

This module defines protocols for OpenTelemetry-compatible tracing interfaces.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from typing import Self


@runtime_checkable
class TracerProtocol(Protocol):
    """Protocol for OpenTelemetry-compatible tracers."""

    def start_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        context: Any | None = None,
    ) -> SpanProtocol:
        """Start a new span.

        Args:
            name: Span name
            attributes: Optional span attributes
            context: Optional parent context (from extract_context)

        Returns:
            New span instance
        """
        ...

    def get_current_span(self) -> SpanProtocol | None:
        """Get the currently active span.

        Returns:
            Current span or None
        """
        ...

    def inject_context(
        self, carrier: dict[str, str], context: Any | None = None
    ) -> None:
        """Inject trace context into a carrier dict (W3C traceparent).

        Implementations should write a ``traceparent`` key (and optionally
        ``tracestate``) into *carrier* so that downstream consumers can
        continue the distributed trace.

        Args:
            carrier: Mutable dict that will receive the trace headers.
            context: Optional explicit context to inject. If None, uses the
                current active span's context.
        """
        ...

    def extract_context(self, carrier: dict[str, str]) -> Any | None:
        """Extract trace context from a carrier dict (W3C traceparent).

        Args:
            carrier: Dict containing trace headers (e.g. message headers).

        Returns:
            An opaque context object suitable for passing to ``start_span``,
            or *None* if no valid context was found.
        """
        ...


@runtime_checkable
class SpanProtocol(Protocol):
    """Protocol for OpenTelemetry-compatible spans."""

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a span attribute.

        Args:
            key: Attribute key
            value: Attribute value
        """
        ...

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add an event to the span.

        Args:
            name: Event name
            attributes: Optional event attributes
        """
        ...

    def record_exception(self, exception: Exception) -> None:
        """Record an exception on the span.

        Args:
            exception: Exception to record
        """
        ...

    def set_status(self, status: str) -> None:
        """Set the span status.

        Args:
            status: Status string
        """
        ...

    def __enter__(self) -> Self:
        """Enter the span context (for 'with' statement)."""
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Exit the span context."""
        ...

    def end(self) -> None:
        """Mark span as finished.

        Called automatically by __exit__, but can be called explicitly
        for early ending of a span.
        """
        ...


__all__ = ["SpanProtocol", "TracerProtocol"]
