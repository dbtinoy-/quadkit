"""Request ID accessors and log filtering.

The middleware that assigns the request ID and writes the ``X-Request-ID``
response header is ``RequestContextMiddleware`` in
``quadkit.web.middleware.request_context`` — the single implementation the
default stack mounts. This module holds the readers that consume the id it
assigns: the per-request accessor and the logging filter.
"""

from __future__ import annotations

from starlette.requests import Request

from quadkit.logging import get_logger
from quadkit.primitives.context import REQUEST_ID, Context


def get_request_id_from_request(request: Request) -> str | None:
    """Get request ID from request state.

    Args:
        request: Quadkit request.

    Returns:
        Request ID or None.

    Example:
        >>> @app.get("/api/status")
        >>> async def get_status(request: Request):
        ...     request_id = get_request_id_from_request(request)
        ...     return {"request_id": request_id}
    """
    return getattr(request.state, "request_id", None)


class RequestIDLogFilter:
    """Log filter to add request ID to log records.

    This filter extracts the current request ID from the injected Context
    and adds it to each log record as `request_id`.
    """

    def __init__(self, ctx: Context | None = None) -> None:
        """Initialize filter.

        Args:
            ctx: Application context instance. If provided, the request ID
                is read via ``ctx.get(REQUEST_ID)``.
        """
        self._ctx = ctx

    def filter(self, record: object) -> bool:
        """Add request ID to log record."""
        request_id = self._ctx.get(REQUEST_ID) if self._ctx is not None else None
        record.request_id = request_id or "no_request"  # type: ignore[attr-defined]
        return True


def configure_logging_with_request_id() -> None:
    """Configure standard logging to include request ID.

    This adds a filter to the root logger to ensure all logs include the
    current request ID if available.
    """

    root_logger = get_logger()
    if not any(isinstance(f, RequestIDLogFilter) for f in root_logger.filters):
        root_logger.addFilter(RequestIDLogFilter())
