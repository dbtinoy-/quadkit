"""Tests for monitor tracing types."""

import pytest

from quadkit.monitor.tracing.core import SpanContext, SpanKind, SpanStatus


class TestSpanKind:
    """Tests for SpanKind enum."""

    def test_span_kind_values(self) -> None:
        """Test SpanKind enum values."""
        assert SpanKind.INTERNAL.value == "internal"
        assert SpanKind.SERVER.value == "server"
        assert SpanKind.CLIENT.value == "client"
        assert SpanKind.PRODUCER.value == "producer"
        assert SpanKind.CONSUMER.value == "consumer"

    def test_span_kind_members(self) -> None:
        """Test SpanKind has expected members."""
        members = list(SpanKind)
        assert len(members) == 5


class TestSpanStatus:
    """Tests for SpanStatus enum."""

    def test_span_status_values(self) -> None:
        """Test SpanStatus enum values."""
        assert SpanStatus.UNSET.value == "unset"
        assert SpanStatus.OK.value == "ok"
        assert SpanStatus.ERROR.value == "error"

    def test_span_status_members(self) -> None:
        """Test SpanStatus has expected members."""
        members = list(SpanStatus)
        assert len(members) == 3


class TestSpanContext:
    """Tests for SpanContext dataclass."""

    def test_span_context_defaults(self) -> None:
        """Test SpanContext default values."""
        ctx = SpanContext(trace_id="abc", span_id="123")
        assert ctx.trace_id == "abc"
        assert ctx.span_id == "123"
        assert ctx.parent_span_id is None
        assert ctx.trace_flags == 0x01
        assert ctx.trace_state == ""
        assert ctx.sampled is True

    def test_span_context_with_parent(self) -> None:
        """Test SpanContext with parent."""
        ctx = SpanContext(
            trace_id="abc",
            span_id="123",
            parent_span_id="parent",
        )
        assert ctx.parent_span_id == "parent"
