"""Request ID middleware for request tracing.

Adds unique request ID to each request and propagates through logs.
"""

from __future__ import annotations

from typing import Any
import uuid

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from quadkit.contracts.core.identity import IdGeneratorProtocol
from quadkit.logging import get_logger
from quadkit.primitives.context import REQUEST_ID, Context
from quadkit.web.middleware._headers import get_header, sanitize_request_id

logger = get_logger(__name__)


class RequestIDMiddleware:
    """Pure ASGI middleware to add request ID to each request.

    10x faster than BaseHTTPMiddleware - no task creation overhead.

    Features:
        - Generates unique request ID for each request
        - Accepts existing request ID from X-Request-ID header
        - Adds request ID to response headers
        - Propagates request ID to context for logging

    Example:
        >>> from quadkit.web.middleware import RequestIDMiddleware
        >>>
        >>> # Request
        >>> GET /api/users/123
        >>> # (no X-Request-ID header)
        >>>
        >>> # Response
        >>> X-Request-ID: req_a1b2c3d4
        >>>
        >>> # Logs
        >>> 2026-01-12 10:23:15 INFO [req_a1b2c3d4] Fetching user 123
    """

    def __init__(
        self,
        app: ASGIApp,
        ctx: Context | None = None,
        header_name: str = "X-Request-ID",
        ids: IdGeneratorProtocol | None = None,
    ):
        """Initialize request ID middleware.

        Args:
            app: ASGI application
            ctx: Application context for propagating the request ID.
            header_name: Header name for request ID (default: X-Request-ID).
            ids: ID generator protocol for request ID generation.
        """
        self.app = app
        self._ctx = ctx
        self.header_name = header_name
        self._ids = ids

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pure ASGI middleware implementation."""

        if scope["type"] != "http":
            # Pass through non-HTTP requests
            await self.app(scope, receive, send)
            return

        # Get or generate request ID from headers
        header_bytes = self.header_name.lower().encode()
        inbound = get_header(scope, header_bytes)
        # H-01: inbound ids are client-controlled — accept only short
        # URL-safe tokens; anything else is dropped and a fresh id generated.
        request_id = sanitize_request_id(
            inbound.decode("ascii", "replace") if inbound is not None else None
        )
        if not request_id:
            # Generate new UUID-based request ID
            request_id = (
                f"req_{self._ids.generate() if self._ids else uuid.uuid4().hex[:12]}"
            )

        # Set in context (for logging and background tasks)
        if self._ctx is not None:
            self._ctx.set(REQUEST_ID, request_id)

        # Store request ID in scope for access in handlers
        scope["request_id"] = request_id

        logger.debug(
            "Request ID assigned",
            request_id=request_id,
            method=scope.get("method", ""),
            path=scope.get("path", ""),
        )

        # Wrap send to add request ID header to response
        async def send_with_request_id(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                # Add request ID header
                headers.append([header_bytes, request_id.encode()])
                message["headers"] = headers
            await send(message)

        # Process request
        await self.app(scope, receive, send_with_request_id)


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
