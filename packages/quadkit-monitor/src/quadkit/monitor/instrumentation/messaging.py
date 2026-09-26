"""OpenTelemetry instrumentation for messaging (email, SMS, push).

Provides automatic tracing and metrics for message publishing and consuming.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import time
from typing import Any

from quadkit.logging import get_logger

try:
    from opentelemetry import metrics, trace
    from opentelemetry.propagate import inject
    from opentelemetry.trace import Span, StatusCode

    _opentelemetry_available = True
except (ImportError, NameError):
    _opentelemetry_available = False

    class _DummySpan:
        def __enter__(self) -> Any:
            return self

        def __exit__(self, *args: object) -> Any:
            pass

        def set_attribute(self, *args: Any) -> Any:
            pass

        def record_exception(self, *args: Any) -> Any:
            pass

        def set_status(self, *args: Any) -> Any:
            pass

    class _DummyTracer:
        def start_as_current_span(self, *args: Any, **kwargs: Any) -> Any:
            return _DummySpan()

    class _DummyCounter:
        def add(self, *args: Any, **kwargs: Any) -> Any:
            pass

    class _DummyHistogram:
        def record(self, *args: Any, **kwargs: Any) -> Any:
            pass

    class _DummyMeter:
        def create_counter(self, *args: Any, **kwargs: Any) -> Any:
            return _DummyCounter()

        def create_histogram(self, *args: Any, **kwargs: Any) -> Any:
            return _DummyHistogram()

    def _dummy_status(*args: Any) -> Any:
        return None

    def _dummy_inject(*args: Any, **kwargs: Any) -> None:
        return None

    metrics = type(
        "metrics",
        (),
        {"get_meter": lambda *_: _DummyMeter()},
    )()
    trace = type(
        "trace",
        (),
        {
            "get_tracer": lambda *_: _DummyTracer(),
            "Status": _dummy_status,
            "SpanKind": type(
                "SpanKind",
                (),
                {"PRODUCER": 1, "CONSUMER": 2, "CLIENT": 3, "SERVER": 4},
            )(),
        },
    )()
    inject = _dummy_inject
    StatusCode = type("StatusCode", (), {"OK": 0, "ERROR": 2})()

logger = get_logger(__name__)
_OTEL_INSTALL_HINT = "pip install quadkit-monitor[otel]"

tracer = trace.get_tracer("quadkit.messaging")
meter = metrics.get_meter("quadkit.messaging")

# Metrics
messages_published = meter.create_counter(
    "messaging.messages_published_total",
    unit="1",
    description="Total number of messages published",
)

messages_consumed = meter.create_counter(
    "messaging.messages_consumed_total",
    unit="1",
    description="Total number of messages consumed",
)

message_duration = meter.create_histogram(
    "messaging.operation_duration",
    unit="ms",
    description="Duration of messaging operations",
)

message_errors = meter.create_counter(
    "messaging.errors_total",
    unit="1",
    description="Total number of messaging errors",
)


@asynccontextmanager
async def trace_publish(
    channel: str,
    message_type: str = "email",
    recipient: str | None = None,
    **attributes: Any,
) -> AsyncGenerator[Span, None]:
    """Context manager for tracing message publishing.

    Usage:
        async with trace_publish("notifications", "email", "user@example.com") as span:
            await send_email(...)
    """
    if not _opentelemetry_available:
        logger.warning(
            "opentelemetry_not_available",
            hint=_OTEL_INSTALL_HINT,
            detail="message publishing tracing disabled",
        )
        yield _DummySpan()
        return
    start_time = time.time()
    span_name = f"publish {message_type}"

    with tracer.start_as_current_span(
        span_name,
        kind=trace.SpanKind.PRODUCER,
    ) as span:
        span.set_attribute("messaging.system", "quadkit")
        span.set_attribute("messaging.operation", "publish")
        span.set_attribute("messaging.destination", channel)
        span.set_attribute("messaging.message_type", message_type)

        if recipient:
            # Redact full recipient for privacy
            span.set_attribute(
                "messaging.recipient_type",
                _get_recipient_type(recipient),
            )

        for key, value in attributes.items():
            span.set_attribute(f"messaging.{key}", str(value))

        try:
            yield span
            span.set_status(trace.Status(StatusCode.OK))
            messages_published.add(
                1,
                {
                    "messaging.message_type": message_type,
                    "messaging.destination": channel,
                },
            )
        except Exception as e:  # noqa: BLE001 — record every failure on the span + metrics, then re-raise
            span.record_exception(e)
            span.set_status(trace.Status(StatusCode.ERROR, str(e)))
            message_errors.add(
                1,
                {
                    "messaging.message_type": message_type,
                    "messaging.destination": channel,
                },
            )
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            message_duration.record(
                duration_ms,
                {
                    "messaging.operation": "publish",
                    "messaging.message_type": message_type,
                },
            )


@asynccontextmanager
async def trace_consume(
    channel: str,
    message_type: str = "unknown",
    carrier: dict[str, Any] | None = None,
    **attributes: Any,
) -> AsyncGenerator[Span, None]:
    """Context manager for tracing message consumption.

    Usage:
        async with trace_consume("notifications", carrier=headers) as span:
            await process_message(...)
    """
    if not _opentelemetry_available:
        logger.warning(
            "opentelemetry_not_available",
            hint=_OTEL_INSTALL_HINT,
            detail="message consuming tracing disabled",
        )
        yield _DummySpan()
        return
    start_time = time.time()
    span_name = f"consume {message_type}"

    # Extract parent context from carrier if provided
    parent_context = None
    if carrier:
        from opentelemetry.propagate import extract

        parent_context = extract(carrier)

    with tracer.start_as_current_span(
        span_name,
        context=parent_context,
        kind=trace.SpanKind.CONSUMER,
    ) as span:
        span.set_attribute("messaging.system", "quadkit")
        span.set_attribute("messaging.operation", "consume")
        span.set_attribute("messaging.destination", channel)
        span.set_attribute("messaging.message_type", message_type)

        for key, value in attributes.items():
            span.set_attribute(f"messaging.{key}", str(value))

        try:
            yield span
            span.set_status(trace.Status(StatusCode.OK))
            messages_consumed.add(
                1,
                {
                    "messaging.message_type": message_type,
                    "messaging.destination": channel,
                },
            )
        except Exception as e:  # noqa: BLE001 — record every failure on the span + metrics, then re-raise
            span.record_exception(e)
            span.set_status(trace.Status(StatusCode.ERROR, str(e)))
            message_errors.add(
                1,
                {
                    "messaging.message_type": message_type,
                    "messaging.destination": channel,
                },
            )
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            message_duration.record(
                duration_ms,
                {
                    "messaging.operation": "consume",
                    "messaging.message_type": message_type,
                },
            )


def inject_trace_context(carrier: dict[str, Any]) -> None:
    """Inject current trace context into carrier for propagation.

    Call this before sending a message to propagate trace context.
    """
    if not _opentelemetry_available:
        logger.warning(
            "opentelemetry_not_available",
            hint=_OTEL_INSTALL_HINT,
            detail="trace context injection disabled",
        )
        return
    inject(carrier)


def _get_recipient_type(recipient: str) -> str:
    """Determine recipient type from address format."""
    if "@" in recipient:
        return "email"
    if recipient.startswith("+"):
        return "phone"
    return "device_token"


__all__ = [
    "inject_trace_context",
    "message_duration",
    "message_errors",
    "messages_consumed",
    "messages_published",
    "trace_consume",
    "trace_publish",
]
