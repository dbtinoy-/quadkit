"""Observability middleware — timing, logging, and correlation ID tracking."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any
import uuid

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.middleware.types import NextHandler

logger = get_logger(__name__)


class TimingMiddleware:
    """Middleware that measures and logs execution duration.

    Wraps the next handler and logs the elapsed time in milliseconds.
    The timing is added to the context as ``_timing_ms``.
    """

    __slots__ = ("_name",)

    def __init__(self, name: str = "timing") -> None:
        self._name = name

    async def __call__(self, context: Any, next_handler: NextHandler) -> Any:
        """Measure execution time and log it."""
        start = time.perf_counter()
        try:
            return await next_handler(context)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            try:
                context._timing_ms = elapsed_ms
            except (AttributeError, TypeError):
                logger.debug(
                    "timing_context_attach_failed", context_type=type(context).__name__
                )
            logger.debug(
                "middleware_timing",
                middleware=self._name,
                elapsed_ms=round(elapsed_ms, 2),
            )


class LoggingMiddleware:
    """Middleware that logs entry and exit of the processing pipeline.

    Logs at debug level on entry and at info level on completion or error.
    """

    __slots__ = ("_name",)

    def __init__(self, name: str = "logging") -> None:
        self._name = name

    async def __call__(self, context: Any, next_handler: NextHandler) -> Any:
        """Log entry, exit, and errors."""
        context_type = type(context).__name__
        logger.debug(
            "middleware_enter",
            middleware=self._name,
            context_type=context_type,
        )
        try:
            result = await next_handler(context)
            logger.debug(
                "middleware_exit",
                middleware=self._name,
                context_type=context_type,
                status="success",
            )
            return result
        except Exception:  # noqa: BLE001 — middleware errors must not crash the host
            logger.exception(
                "middleware_error",
                middleware=self._name,
                context_type=context_type,
                status="error",
            )
            raise


class CorrelationIdMiddleware:
    """Middleware that attaches a correlation ID to the processing context.

    If the context already has a ``correlation_id`` attribute, it is
    preserved. Otherwise a new UUID4 is generated and set.

    Args:
        header: attribute name to read/write on the context.
    """

    __slots__ = ("_header",)

    def __init__(self, header: str = "correlation_id") -> None:
        self._header = header

    async def __call__(self, context: Any, next_handler: NextHandler) -> Any:
        """Ensure a correlation ID is present, bind it to structlog contextvars, then pass through."""
        existing = getattr(context, self._header, None)
        cid = existing or str(uuid.uuid4())
        if existing is None:
            try:
                setattr(context, self._header, cid)
            except (AttributeError, TypeError):
                logger.debug(
                    "correlation_id_attach_failed",
                    header=self._header,
                    context_type=type(context).__name__,
                )
        logger.debug(
            "middleware_correlation_id",
            correlation_id=cid,
        )
        try:
            import structlog.contextvars as _sv

            _sv.bind_contextvars(correlation_id=cid)
            try:
                return await next_handler(context)
            finally:
                _sv.unbind_contextvars("correlation_id")
        except ImportError:
            return await next_handler(context)


__all__ = ["CorrelationIdMiddleware", "LoggingMiddleware", "TimingMiddleware"]
