"""Web middleware and exception filter protocols."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class WebMiddlewareProtocol(Protocol):
    """Protocol for HTTP web middleware.

    WebMiddlewareProtocol intercepts HTTP requests and responses for cross-cutting
    concerns such as authentication, logging, CORS, and compression.

    This is distinct from ``MiddlewareProtocol`` in ``contracts.middleware``
    which is transport-agnostic (events, commands, queries). WebMiddlewareProtocol is
    exclusively for the HTTP request/response lifecycle in ``quadkit-web``
    and compatible ASGI frameworks.

    Example::

        class LoggingMiddleware:
            async def __call__(self, request, call_next):
                start = time.monotonic()
                response = await call_next(request)
                logger.info("%s %s %.2fs", request.method, request.url, time.monotonic()-start)
                return response
    """

    async def __call__(
        self,
        request: Any,
        call_next: Any,
    ) -> Any:
        """Process the HTTP request.

        Args:
            request: Incoming HTTP request.
            call_next: Callable to invoke the next middleware/handler.

        Returns:
            HTTP response.
        """
        ...


@runtime_checkable
class ExceptionFilterProtocol(Protocol):
    """Protocol for exception handling filters.

    Exception filters convert exceptions to HTTP responses.

    Example:
        ```python
        class ValidationExceptionFilter:
            def can_handle(self, exc):
                return isinstance(exc, ValidationError)

            def handle(self, exc, request):
                return JSONResponse(
                    {"errors": exc.errors()},
                    status_code=422,
                )
        ```
    """

    def can_handle(self, exc: Exception) -> bool:
        """Check if this filter handles the exception.

        Args:
            exc: Exception to check.

        Returns:
            True if this filter can handle the exception.
        """
        ...

    def handle(self, exc: Exception, request: Any) -> Any:
        """Convert exception to a response.

        Args:
            exc: Exception to handle.
            request: Original request.

        Returns:
            HTTP response.
        """
        ...


__all__ = [
    "ExceptionFilterProtocol",
    "WebMiddlewareProtocol",
]
