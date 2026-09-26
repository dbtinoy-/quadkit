"""HTTP instrumentation for OpenTelemetry.

This module provides the OTelMiddleware class for automatically
instrumenting HTTP requests with OpenTelemetry tracing and metrics.

Features:
- Automatic span creation for each HTTP request
- Parent context extraction from incoming headers
- Request count and duration metrics
- HTTP status code and error tracking

Example:
    >>> from quadkit.monitor import OTelMiddleware
    >>>
    >>> app = OTelMiddleware(my_asgi_app)
    >>> # All HTTP requests are now automatically traced
"""

from __future__ import annotations

import time
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

# Try to import opentelemetry, but handle the case where it's broken
try:
    from opentelemetry import metrics, trace
    from opentelemetry.propagate import extract
    from opentelemetry.semconv.trace import (
        SpanAttributes,
    )

    _opentelemetry_available = True
except (ImportError, NameError):
    # OpenTelemetry has import issues or is not available
    _opentelemetry_available = False

    # Create dummy classes to avoid import errors
    class _DummyTracer:
        def start_as_current_span(self, *args: Any, **kwargs: Any) -> Any:
            return _DummySpan()

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

    class _DummyMeter:
        def create_counter(self, *args: Any, **kwargs: Any) -> Any:
            return _DummyCounter()

        def create_histogram(self, *args: Any, **kwargs: Any) -> Any:
            return _DummyHistogram()

    class _DummyCounter:
        def add(self, *args: Any, **kwargs: Any) -> Any:
            pass

    class _DummyHistogram:
        def record(self, *args: Any, **kwargs: Any) -> Any:
            pass

    metrics = type("metrics", (), {"get_meter": lambda *_: _DummyMeter()})()
    trace = type("trace", (), {"get_tracer": lambda *_: _DummyTracer()})()

    def extract(*args: Any) -> Any:
        return None

    SpanAttributes = type(
        "SpanAttributes",
        (),
        {
            "HTTP_METHOD": "http.method",
            "HTTP_TARGET": "http.target",
            "HTTP_FLAVOR": "http.flavor",
            "HTTP_SCHEME": "http.scheme",
            "HTTP_STATUS_CODE": "http.status_code",
        },
    )()


class OTelMiddleware:
    """Middleware for OpenTelemetry tracing and metrics in Quadkit-Web.

    Provides automatic tracing and metrics collection for HTTP requests.
    Gracefully degrades when OpenTelemetry is not available or has import issues.

    Features:
    - Automatic span creation for each HTTP request
    - Extracts parent trace context from incoming headers
    - Records request count and duration metrics
    - Captures HTTP status codes and error conditions

    Example:
        >>> from quadkit.monitor import OTelMiddleware
        >>>
        >>> app = OTelMiddleware(my_asgi_app)
    """

    def __init__(self, app: ASGIApp):
        """Initialize the OTel middleware.

        Args:
            app: The ASGI application to wrap.
        """
        self.app = app
        if _opentelemetry_available:
            self.tracer = trace.get_tracer("quadkit.web")
            self.meter = metrics.get_meter("quadkit.web")
            self.request_counter = self.meter.create_counter(
                "http.server.request_count",
                unit="1",
                description="Total number of HTTP requests",
            )
            self.request_duration = self.meter.create_histogram(
                "http.server.duration",
                unit="ms",
                description="Duration of HTTP requests",
            )
        else:
            self.tracer = None
            self.meter = None
            self.request_counter = None
            self.request_duration = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process an HTTP request and record tracing and metrics.

        Args:
            scope: The ASGI scope dictionary.
            receive: The ASGI receive callable.
            send: The ASGI send callable.

        Note:
            This method automatically creates spans, extracts parent context,
            records metrics, and handles error cases.
        """
        if not _opentelemetry_available or self.tracer is None:
            # If OpenTelemetry is not available, just pass through
            await self.app(scope, receive, send)
            return

        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        # Extract parent context from headers
        headers_dict = {
            k.decode("utf-8"): v.decode("utf-8") for k, v in scope.get("headers", [])
        }
        parent_context = extract(headers_dict)

        path = scope.get("path", "")
        method = scope.get("method", "")

        span_name = f"{method} {path}"

        with self.tracer.start_as_current_span(
            span_name,
            context=parent_context,
            kind=trace.SpanKind.SERVER,
        ) as span:
            span.set_attribute(SpanAttributes.HTTP_METHOD, method)
            span.set_attribute(SpanAttributes.HTTP_TARGET, path)
            span.set_attribute(
                SpanAttributes.HTTP_FLAVOR,
                scope.get("http_version", ""),
            )
            span.set_attribute(SpanAttributes.HTTP_SCHEME, scope.get("scheme", ""))

            # Wrap send to capture status code
            status_code = [200]  # Use a list to allow mutation in nested function

            async def send_wrapper(message: Any) -> None:
                if message["type"] == "http.response.start":
                    status = message["status"]
                    status_code[0] = status
                    span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, status)
                    if status >= 400:
                        span.set_status(trace.Status(trace.StatusCode.ERROR))
                await send(message)

            try:
                await self.app(scope, receive, send_wrapper)
            except Exception as e:  # noqa: BLE001 — record every request failure on the span, then re-raise
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                status_code[0] = 500
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                attributes = {
                    "http.method": method,
                    "http.target": path,
                    "http.status_code": status_code[0],
                }
                self.request_counter.add(1, attributes)
                self.request_duration.record(
                    duration_ms,
                    {"http.method": method, "http.status_code": status_code[0]},
                )
