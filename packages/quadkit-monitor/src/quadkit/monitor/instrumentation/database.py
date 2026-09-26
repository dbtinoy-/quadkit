"""Database instrumentation for OpenTelemetry.

This module provides functions for instrumenting database providers
with OpenTelemetry tracing and metrics.

Example:
    >>> from quadkit.monitor import instrument_database
        >>> from quadkit.sql import DatabaseService
    >>>
    >>> provider = DatabaseService(config)
    >>> instrument_database(provider)
    >>> # All queries are now automatically traced
"""

from __future__ import annotations

import time
from typing import Any

from quadkit.logging import get_logger

try:
    from opentelemetry import metrics, trace
    from opentelemetry.semconv.trace import (
        SpanAttributes,
    )

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

    metrics = type(
        "metrics",
        (),
        {"get_meter": lambda *_: _DummyMeter()},
    )()
    trace = type(
        "trace",
        (),
        {"get_tracer": lambda *_: _DummyTracer()},
    )()
    SpanAttributes = type("SpanAttributes", (), {})()

logger = get_logger(__name__)
_OTEL_INSTALL_HINT = "pip install quadkit-monitor[otel]"


def _otel_warning() -> None:
    """Emit a one-off warning when OpenTelemetry is not installed."""

    logger.warning(
        "opentelemetry_not_available",
        hint=_OTEL_INSTALL_HINT,
        detail="database instrumentation disabled",
    )


def instrument_database(provider: Any) -> None:
    """Instrument a Quadkit DatabaseService with OpenTelemetry tracing.

    Wraps the provider's execute and execute_query methods to automatically
    create spans and record metrics for each database operation.

    Features:
    - Automatic span creation for each query
    - Query duration tracking
    - Error recording and status tracking
    - Metrics for query count and duration

    Args:
        provider: The database provider to instrument. Must have 'execute'
            and optionally 'execute_query' methods.

    Example:
        >>> from quadkit.monitor import instrument_database
            >>> from quadkit.sql import DatabaseService
        >>>
        >>> provider = DatabaseService(config)
        >>> instrument_database(provider)
        >>> # Queries are now automatically traced
    """
    if not _opentelemetry_available:
        _otel_warning()
        return
    if hasattr(provider, "_traced"):
        return

    original_execute = provider.execute
    tracer = trace.get_tracer("quadkit.sql")
    meter = metrics.get_meter("quadkit.sql")

    query_counter = meter.create_counter(
        "db.client.query_count",
        unit="1",
        description="Total number of database queries",
    )
    query_duration = meter.create_histogram(
        "db.client.duration",
        unit="ms",
        description="Duration of database queries",
    )

    async def traced_execute(sql: str, params: Any = None) -> Any:
        start_time = time.time()
        # Determine system from URL
        db_system = "other"
        url = getattr(provider, "url", "")
        if "sqlite" in url:
            db_system = "sqlite"
        elif "postgres" in url:
            db_system = "postgresql"
        elif "mysql" in url:
            db_system = "mysql"

        with tracer.start_as_current_span(
            "db.execute",
            kind=trace.SpanKind.CLIENT,
            attributes={
                SpanAttributes.DB_SYSTEM: db_system,
                SpanAttributes.DB_STATEMENT: sql,
                SpanAttributes.DB_NAME: getattr(provider.config, "name", "database"),
            },
        ) as span:
            try:
                result = await original_execute(sql, params)
                success = hasattr(result, "success") and result.success
                if not success:
                    span.set_status(
                        trace.Status(
                            trace.StatusCode.ERROR,
                            getattr(result, "error_message", "Unknown error"),
                        ),
                    )

                # Record metrics
                duration_ms = (time.time() - start_time) * 1000
                attributes = {
                    "db.system": db_system,
                    "db.operation": sql.split(maxsplit=1)[0].upper()
                    if sql
                    else "UNKNOWN",
                    "db.success": success,
                }
                query_counter.add(1, attributes)
                query_duration.record(duration_ms, attributes)

                return result
            except Exception as e:  # noqa: BLE001 — record every query failure on the span + metrics, then re-raise
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))

                # Record error metrics
                duration_ms = (time.time() - start_time) * 1000
                attributes = {
                    "db.system": db_system,
                    "db.operation": sql.split(maxsplit=1)[0].upper()
                    if sql
                    else "UNKNOWN",
                    "db.success": False,
                }
                query_counter.add(1, attributes)
                query_duration.record(duration_ms, attributes)
                raise

    provider.execute = traced_execute
    # Also wrap execute_query if it exists separately
    if hasattr(provider, "execute_query"):
        original_query = provider.execute_query

        async def traced_query(sql: str, params: Any = None) -> Any:
            # Determine system from URL (same as traced_execute)
            db_system = "other"
            url = getattr(provider, "url", "")
            if "sqlite" in url:
                db_system = "sqlite"
            elif "postgres" in url:
                db_system = "postgresql"
            elif "mysql" in url:
                db_system = "mysql"

            with tracer.start_as_current_span(
                "db.query",
                kind=trace.SpanKind.CLIENT,
                attributes={
                    SpanAttributes.DB_SYSTEM: db_system,
                    SpanAttributes.DB_STATEMENT: sql,
                },
            ) as span:
                try:
                    return await original_query(sql, params)
                except Exception as e:  # noqa: BLE001 — record every query failure on the span, then re-raise
                    span.record_exception(e)
                    raise

        provider.execute_query = traced_query

    provider._traced = True
