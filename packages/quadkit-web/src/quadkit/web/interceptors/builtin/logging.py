"""Logging interceptor for request/response logging.

Provides structured logging for HTTP requests and responses.
"""

from __future__ import annotations

from typing import Any, cast

from quadkit.logging import get_logger
from quadkit.primitives import clock as ambient_clock
from quadkit.web.protocols import (
    CallHandlerProtocol,
    ExecutionContextProtocol,
    WebInterceptorProtocol,
)

logger = get_logger(__name__)


class LoggingInterceptor(WebInterceptorProtocol):
    """Interceptor that logs request and response information.

    **Development/debug only** — not intended for production use.
    For production request logging, use ``AccessLogMiddleware`` instead.

    Logs the request method, path, status code, and elapsed time
    for each HTTP request.

    Example:
        ```python
        # Add to global interceptors
        router.add_interceptor(LoggingInterceptor())

        # Or use decorator
        @use_interceptors(LoggingInterceptor())
        class UserController(Controller):
            ...
        ```
    """

    def __init__(
        self,
        log_request: bool = True,
        log_response: bool = True,
        log_body: bool = False,
        logger_name: str | None = None,
    ):
        """Initialize the logging interceptor.

        Args:
            log_request: Whether to log incoming requests.
            log_response: Whether to log responses.
            log_body: Whether to log request/response bodies (careful with sensitive data).
            logger_name: Custom logger name to use.
        """
        self._log_request = log_request
        self._log_response = log_response
        self._log_body = log_body
        self._logger = get_logger(logger_name or __name__)

    async def intercept(
        self,
        context: ExecutionContextProtocol,
        next_handler: CallHandlerProtocol,
    ) -> Any:
        """Intercept the request and log details.

        Args:
            context: The execution context with request info.
            next_handler: The next handler in the chain.

        Returns:
            The response from the handler.
        """
        request = context.request
        method = getattr(request, "method", "UNKNOWN")
        url = getattr(request, "url", None)
        path = url.path if url and hasattr(url, "path") else "/"

        # Log incoming request
        if self._log_request:
            extra = {
                "method": method,
                "path": path,
                "client": self._get_client_ip(request),
            }

            if self._log_body and hasattr(request, "body"):
                # Don't await here to not block
                extra["body_size"] = request.headers.get("content-length", "unknown")

            cast("Any", self._logger).info(
                "Request: %s %s",
                method,
                path,
                extra=extra,
            )

        # Track timing
        start_time = ambient_clock.monotonic()

        try:
            # Call the next handler
            result = await next_handler.handle()

            # Calculate elapsed time
            elapsed = (ambient_clock.monotonic() - start_time) * 1000  # ms

            # Log response
            if self._log_response:
                status_code = getattr(result, "status_code", 200) if result else 500
                cast("Any", self._logger).info(
                    "Response: %s %s - %s (%.1fms)",
                    method,
                    path,
                    status_code,
                    elapsed,
                    extra={
                        "method": method,
                        "path": path,
                        "status_code": status_code,
                        "elapsed_ms": elapsed,
                    },
                )

            return result

        except Exception as e:
            # Log error
            elapsed = (ambient_clock.monotonic() - start_time) * 1000
            cast("Any", self._logger).error(
                "Error: %s %s - %s: %s (%.1fms)",
                method,
                path,
                type(e).__name__,
                e,
                elapsed,
                extra={
                    "method": method,
                    "path": path,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "elapsed_ms": elapsed,
                },
                exc_info=True,
            )
            raise

    def _get_client_ip(self, request: Any) -> str:
        """Extract client IP from request.

        Args:
            request: The HTTP request.

        Returns:
            The client IP address.
        """
        # Check X-Forwarded-For header
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return cast("str", forwarded.split(",")[0].strip())

        # Fall back to direct client
        client = getattr(request, "client", None)
        if client:
            return cast("str", client.host)
        return "unknown"


__all__ = ["LoggingInterceptor"]
