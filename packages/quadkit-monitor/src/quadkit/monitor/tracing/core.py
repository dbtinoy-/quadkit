"""Distributed tracing core implementation."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import StrEnum
import random
import time
from typing import Any, Protocol, Self

from quadkit.contracts.observability.tracing import SpanProtocol, TracerProtocol
from quadkit.contracts.observability.tracing import TracerProtocol as TraceProvider
from quadkit.logging import get_logger
from quadkit.monitor.constants import DEFAULT_MAX_SPANS

logger = get_logger(__name__)
_current_span: ContextVar[Span | None] = ContextVar("current_span", default=None)


class SpanKind(StrEnum):
    """Span kind following OpenTelemetry specification."""

    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


class SpanStatus(StrEnum):
    """Span status following OpenTelemetry specification."""

    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


@dataclass
class SpanContext:
    """Span context for propagation."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    trace_flags: int = 0x01
    trace_state: str = ""
    sampled: bool = True

    def to_traceparent(self) -> str:
        return f"00-{self.trace_id}-{self.span_id}-{self.trace_flags:02x}"

    @classmethod
    def from_traceparent(cls, traceparent: str) -> SpanContext | None:
        try:
            parts = traceparent.split("-")
            if len(parts) != 4:
                return None
            version, trace_id, span_id, flags = parts
            if version != "00":
                return None
            return cls(trace_id=trace_id, span_id=span_id, trace_flags=int(flags, 16))
        except (ValueError, IndexError):
            return None


@dataclass
class Span(SpanProtocol):
    """Distributed tracing span."""

    name: str
    context: SpanContext
    parent_span_id: str | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=128))
    status: SpanStatus = SpanStatus.UNSET
    status_message: str | None = None
    kind: SpanKind = SpanKind.INTERNAL

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        self.events.append(
            {
                "name": name,
                "timestamp": time.time(),
                "attributes": attributes or {},
            },
        )

    def set_status(self, status: str) -> None:
        self.status = SpanStatus(status)
        self.status_message = None

    def record_exception(self, exception: Exception) -> None:
        import traceback

        self.add_event(
            "exception",
            {
                "exception.type": type(exception).__name__,
                "exception.message": str(exception),
                "exception.stacktrace": "".join(
                    traceback.format_exception(
                        type(exception),
                        exception,
                        exception.__traceback__,
                    ),
                ),
            },
        )
        self.status_message = str(exception)
        self.set_status(SpanStatus.ERROR.value)

    def end(self) -> None:
        self.end_time = time.time()

    def __enter__(self) -> Self:
        self._token = _current_span.set(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        if exc_type is not None:
            self.status_message = str(exc_val) if exc_val else None
            self.set_status(SpanStatus.ERROR.value)
            self.add_event(
                "exception",
                {
                    "exception.type": exc_type.__name__,
                    "exception.message": str(exc_val),
                },
            )
        self.end()
        _current_span.reset(self._token)

    def get_duration(self) -> float | None:
        if self.end_time:
            return self.end_time - self.start_time
        return None

    def finish(self) -> None:
        """Alias for end() for compatibility."""
        self.end()


class SpanExporter(Protocol):
    def export(self, spans: list[Span]) -> None: ...


class ConsoleSpanExporter:
    def export(self, spans: list[Span]) -> None:
        for span in spans:
            duration = 0.0
            if span.end_time:
                duration = (span.end_time - span.start_time) * 1000
            logger.info(
                "SPAN: %s | %.2fms | %s",
                span.name,
                duration,
                span.status.value,
            )


class Tracer(TracerProtocol):
    """Distributed tracer logic."""

    def __init__(
        self,
        service_name: str,
        exporter: SpanExporter,
        max_spans: int | None = None,
    ) -> None:
        self.service_name = service_name
        self.exporter = exporter
        self._max_spans: int = max_spans or DEFAULT_MAX_SPANS
        # Bounded deque — oldest spans are automatically evicted when the cap is
        # reached, preventing unbounded memory growth in long-running processes.
        self._spans: deque[Span] = deque(maxlen=self._max_spans)

    def start_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        context: Any | None = None,
        kind: SpanKind = SpanKind.INTERNAL,
    ) -> Span:
        parent = _current_span.get()

        if context:
            trace_id = context.trace_id
            parent_span_id = context.span_id
        elif parent:
            trace_id = parent.context.trace_id
            parent_span_id = parent.context.span_id
        else:
            trace_id = f"{random.getrandbits(128):032x}"
            parent_span_id = None

        span_id = f"{random.getrandbits(64):016x}"

        span = Span(
            name=name,
            context=SpanContext(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_span_id,
            ),
            parent_span_id=parent_span_id,
            kind=kind,
        )

        span.set_attribute("service.name", self.service_name)
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, v)

        # Flush to the exporter when the buffer is full, *before* appending
        # the new span.  The deque's maxlen provides a hard memory cap as a
        # second line of defence against unbounded growth.
        if len(self._spans) >= self._max_spans:
            self.flush()

        self._spans.append(span)

        return span

    def flush(self) -> None:
        if self._spans:
            self.exporter.export(list(self._spans))
            self._spans.clear()

    def get_all_spans(self) -> list[Span]:
        return list(self._spans)

    def get_current_span(self) -> Span | None:
        return _current_span.get()

    def inject_context(
        self,
        carrier: dict[str, str],
        context: SpanContext | None = None,
    ) -> None:
        """Inject trace context into carrier dict."""
        if context is None:
            span = self.get_current_span()
            if span:
                context = span.context

        if context:
            carrier["traceparent"] = context.to_traceparent()

    def extract_context(self, carrier: Mapping[str, str]) -> SpanContext | None:
        """Extract trace context from carrier."""
        traceparent = carrier.get("traceparent")
        if traceparent:
            return SpanContext.from_traceparent(traceparent)
        return None


class InMemoryTraceProvider(TraceProvider):
    """In-memory trace provider using Tracer."""

    def __init__(
        self,
        service_name: str = "quadkit-service",
        max_spans: int = DEFAULT_MAX_SPANS,
        exporter: SpanExporter | None = None,
    ) -> None:
        self.service_name = service_name
        self.exporter = exporter or ConsoleSpanExporter()
        # max_spans eviction is enforced by Tracer._spans which is a
        # deque(maxlen=max_spans).  The oldest spans are automatically
        # discarded when the buffer is full — no unbounded growth possible.
        self.tracer = Tracer(service_name, self.exporter, max_spans=max_spans)

    def create_span(self, name: str, parent: Span | None = None) -> Span:
        context = parent.context if parent else None
        return self.tracer.start_span(name, context=context)

    def start_span(
        self,
        name: str,
        attributes: dict[str, Any] | None = None,
        context: Any | None = None,
    ) -> Span:
        return self.tracer.start_span(name, attributes=attributes, context=context)

    def inject_context(
        self,
        carrier: dict[str, str],
        context: Any | None = None,
    ) -> None:
        self.tracer.inject_context(carrier, context)

    def extract_context(self, carrier: dict[str, str]) -> Any | None:
        return self.tracer.extract_context(carrier)

    def get_current_span(self) -> Span | None:
        return _current_span.get()

    def set_current_span(self, span: Span | None) -> None:
        if span:
            _current_span.set(span)
        else:
            _current_span.set(None)

    def get_all_spans(self) -> list[Span]:
        return self.tracer.get_all_spans()


__all__ = [
    "ConsoleSpanExporter",
    "InMemoryTraceProvider",
    "Span",
    "SpanContext",
    "SpanExporter",
    "SpanKind",
    "SpanStatus",
    "Tracer",
]
