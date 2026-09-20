"""Access log middleware for HTTP request/response logging.

Logs every HTTP request with structured context: method, path, status code,
duration, and request ID. Uses pure ASGI implementation for minimal overhead.

Example output (dev mode):
    2026-01-15 10:23:15 [info] request_completed method=GET path=/api/users
    status=200 duration_ms=12.3 request_id=req_a1b2c3d4

Example output (JSON mode):
    {"event": "request_completed", "method": "GET", "path": "/api/users",
     "status": 200, "duration_ms": 12.3, "request_id": "req_a1b2c3d4", ...}
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.primitives.context import REQUEST_ID, Context
from quadkit.web import constants as const

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from starlette.types import ASGIApp, Receive, Scope, Send

logger = get_logger(__name__)


class AccessLogMiddleware:
    """Pure ASGI middleware for structured HTTP access logging.

    Features:
        - Logs method, path, status code, and duration for every request
        - Automatically includes request_id from context
        - Zero overhead for non-HTTP scopes (websocket, lifespan)
        - Structured output compatible with JSON and console renderers

    Example::

        from quadkit.web.middleware.access_log import AccessLogMiddleware

        app.add_middleware(AccessLogMiddleware)
    """

    def __init__(
        self,
        app: ASGIApp,
        ctx: Context | None = None,
        *,
        exclude_paths: list[str] | None = None,
    ) -> None:
        """Initialize access log middleware.

        Args:
            app: ASGI application.
            ctx: Application context for reading request metadata.
            exclude_paths: Paths to exclude from logging (e.g., ["/health"]).
        """
        self.app = app
        self._ctx = ctx
        self.exclude_paths = set(
            exclude_paths or [const.DEFAULT_HEALTH_PATH, "/healthz", "/ready"]
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """ASGI middleware implementation."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in self.exclude_paths:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        start_time = ambient_clock.monotonic()
        status_code = 500  # Default if response never starts

        async def send_with_logging(message: MutableMapping[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = cast("int", message.get("status", 500))
            await send(message)

        try:
            await self.app(scope, receive, send_with_logging)
        finally:
            duration_ms = round(
                (ambient_clock.monotonic() - start_time) * 1000,
                2,
            )
            request_id = self._ctx.get(REQUEST_ID) if self._ctx else None

            log_kwargs: dict[str, Any] = {
                "method": method,
                "path": path,
                "status": status_code,
                "duration_ms": duration_ms,
            }
            if request_id:
                log_kwargs["request_id"] = request_id

            if status_code >= 500:
                logger.error("request_completed", **log_kwargs)
            elif status_code >= 400:
                logger.warning("request_completed", **log_kwargs)
            else:
                logger.info("request_completed", **log_kwargs)


__all__ = ["AccessLogMiddleware"]
