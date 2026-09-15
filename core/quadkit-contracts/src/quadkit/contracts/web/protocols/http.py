"""HTTP request/response lifecycle protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from datetime import datetime


@runtime_checkable
class HttpRequestLoggerProtocol(Protocol):
    """Protocol for HTTP request/response logging middleware.

    Defines how to log completed HTTP requests with duration, status code,
    and optional metadata for monitoring and audit purposes.

    Example:
        ```python
        class RequestLogger:
            async def log_request(
                self,
                method: str,
                path: str,
                status_code: int,
                duration_ms: float,
                request_id: str | None = None,
                **metadata: Any,
            ) -> None:
                logger.info(
                    "request_completed",
                    method=method,
                    path=path,
                    status=status_code,
                    duration_ms=duration_ms,
                    request_id=request_id,
                    **metadata,
                )
        ```
    """

    async def log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        request_id: str | None = None,
        **metadata: Any,
    ) -> None:
        """Log a completed HTTP request.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: Request path URI.
            status_code: HTTP response status code.
            duration_ms: Request processing duration in milliseconds.
            request_id: Optional request identifier for tracing.
            **metadata: Additional context-specific data (client_id, user_id, etc.).
        """
        ...


@runtime_checkable
class CORSPolicyProtocol(Protocol):
    """Protocol for CORS (Cross-Origin Resource Sharing) policy configuration.

    Defines how to evaluate CORS requests and provide the necessary headers
    and configuration for browser-based clients.

    Example:
        ```python
        class CORSPolicy:
            def is_origin_allowed(self, origin: str) -> bool:
                return origin in ("https://app.example.com", "https://admin.example.com")

            def get_allowed_headers(self) -> list[str]:
                return ["content-type", "authorization", "x-request-id"]

            def get_allowed_methods(self) -> list[str]:
                return ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]

            def get_max_age(self) -> int:
                return 3600
        ```
    """

    def is_origin_allowed(self, origin: str) -> bool:
        """Check if an origin is permitted for CORS requests.

        Args:
            origin: The value of the Origin header from a CORS preflight request.

        Returns:
            True if the origin is allowed, False otherwise.
        """
        ...

    def get_allowed_headers(self) -> list[str]:
        """Return the list of allowed request headers.

        Returns:
            List of header names that clients are allowed to send.
            Common values: ["content-type", "authorization", "x-request-id"].
        """
        ...

    def get_allowed_methods(self) -> list[str]:
        """Return the list of allowed HTTP methods.

        Returns:
            List of HTTP methods clients are allowed to use.
            Typical: ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"].
        """
        ...

    def get_max_age(self) -> int:
        """Return the preflight cache duration in seconds.

        Returns:
            Maximum time (in seconds) browsers should cache preflight
            responses. Typical values: 3600 (1 hour) to 86400 (24 hours).
        """
        ...


@runtime_checkable
class WebRateLimiterProtocol(Protocol):
    """Protocol for web rate limiting.

    Handles rate limiting for HTTP requests based on various scopes.
    """

    async def check_rate_limit(
        self,
        request: Any,
        *,
        max_requests: int,
        window_seconds: int,
        scope: str = "user",
    ) -> None:
        """Check if request is within rate limit.

        Args:
            request: The incoming request.
            max_requests: Maximum requests per window.
            window_seconds: Time window in seconds.
            scope: Rate limit scope (user, ip, or endpoint).

        Raises:
            Exception: If rate limit exceeded.
        """
        ...


@runtime_checkable
class RequestProtocol(Protocol):
    """Protocol for HTTP requests."""

    url: Any
    method: str
    headers: Any
    path_params: dict[str, Any]
    query_params: Any
    cookies: Any
    state: Any
    user: Any
    auth: Any

    async def json(self) -> Any: ...

    async def body(self) -> bytes: ...


@runtime_checkable
class ResponseProtocol(Protocol):
    """Protocol for HTTP responses."""

    status_code: int
    headers: Any
    body: bytes
    media_type: str | None
    background: Any | None

    def set_cookie(
        self,
        key: str,
        value: str = "",
        max_age: int | None = None,
        expires: int | datetime | None = None,
        path: str = "/",
        domain: str | None = None,
        secure: bool = False,
        httponly: bool = False,
        samesite: str = "lax",
    ) -> None: ...

    def delete_cookie(
        self,
        key: str,
        path: str = "/",
        domain: str | None = None,
    ) -> None: ...


@runtime_checkable
class ResponseFactoryProtocol(Protocol):
    """Protocol for creating HTTP responses.

    Abstracts response creation to avoid hard dependencies on specific
    web frameworks (e.g., Starlette/FastAPI) in business logic or middleware.
    """

    def json(
        self,
        content: Any,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> ResponseProtocol:
        """Create a JSON response."""
        ...

    def html(
        self,
        content: str,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> ResponseProtocol:
        """Create an HTML response."""
        ...

    def redirect(
        self,
        url: str,
        status_code: int = 302,
        headers: dict[str, str] | None = None,
    ) -> ResponseProtocol:
        """Create a redirect response."""
        ...
