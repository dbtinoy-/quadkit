"""Tests for distributed tracing."""

import pytest

from quadkit.monitor.tracing import (
    ConsoleSpanExporter,
    SpanContext,
    Tracer,
)


class TestSpanContext:
    """Test span context and propagation."""

    def test_to_traceparent(self):
        """Test traceparent header generation."""
        context = SpanContext(
            trace_id="0af7651916cd43dd8448eb211c80319c",
            span_id="b7ad6b7169203331",
            trace_flags=1,
        )

        traceparent = context.to_traceparent()

        assert traceparent == "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"

    def test_from_traceparent(self):
        """Test traceparent header parsing."""
        traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"

        context = SpanContext.from_traceparent(traceparent)

        assert context is not None
        assert context.trace_id == "0af7651916cd43dd8448eb211c80319c"
        assert context.span_id == "b7ad6b7169203331"
        assert context.trace_flags == 0x01


class TestTracer:
    """Test distributed tracer."""

    def test_start_span_creates_trace_id(self):
        """Test starting span creates trace ID."""
        exporter = ConsoleSpanExporter()
        tracer = Tracer("test-service", exporter)

        span = tracer.start_span("test-operation")

        assert span.context.trace_id
        assert span.context.span_id
        assert len(span.context.trace_id) == 32
        assert len(span.context.span_id) == 16

    def test_child_span_inherits_trace_id(self):
        """Test child span inherits parent trace ID."""
        exporter = ConsoleSpanExporter()
        tracer = Tracer("test-service", exporter)

        with tracer.start_span("parent") as parent:
            child = tracer.start_span("child")

            # Child should have same trace ID
            assert child.context.trace_id == parent.context.trace_id
            # But different span ID
            assert child.context.span_id != parent.context.span_id
            # And parent reference
            assert child.parent_span_id == parent.context.span_id

    def test_extract_inject_context(self):
        """Test context extraction and injection."""
        exporter = ConsoleSpanExporter()
        tracer = Tracer("test-service", exporter)

        # Create span
        span = tracer.start_span("operation")

        # Inject into headers
        headers = {}
        tracer.inject_context(headers, span.context)

        assert "traceparent" in headers

        # Extract from headers
        context = tracer.extract_context(headers)

        assert context is not None
        assert context.trace_id == span.context.trace_id

    def test_span_records_error(self):
        """Test span records exceptions."""
        exporter = ConsoleSpanExporter()
        tracer = Tracer("test-service", exporter)

        with pytest.raises(ValueError):
            with tracer.start_span("failing-op") as span:
                raise ValueError("Test error")

        assert span.status == "error"
        assert len(span.events) == 1
        assert span.events[0]["name"] == "exception"
