"""Web framework error classes.

Aligned with quadkit-contracts exception hierarchy.
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.exceptions import QuadkitError


class HTTPError(QuadkitError):
    """Base HTTP error, compatible with QuadkitError."""

    _code: str = "QK_ERR_WEB_014"

    def __init__(
        self,
        status_code: int,
        detail: str = "",
        headers: dict[str, str] | None = None,
        code: str | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.headers = headers or {}
        self.__cause__ = cause

        super().__init__(
            message=detail,
            details={"status_code": status_code, "headers": self.headers},
            cause=cause,
        )
        self.code = code or f"HTTP_{status_code}"


class NotFoundError(HTTPError):
    """404 Not Found."""

    _code: str = "QK_ERR_WEB_003"

    def __init__(
        self,
        detail: str = "Not Found",
        cause: Exception | None = None,
    ) -> None:
        super().__init__(status_code=404, detail=detail, code="NOT_FOUND", cause=cause)


class BadRequestError(HTTPError):
    """400 Bad Request."""

    _code: str = "QK_ERR_WEB_004"

    def __init__(
        self,
        detail: str = "Bad Request",
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            status_code=400,
            detail=detail,
            code="BAD_REQUEST",
            cause=cause,
        )


class UnauthorizedError(HTTPError):
    """401 Unauthorized."""

    _code: str = "QK_ERR_WEB_005"

    def __init__(
        self,
        detail: str = "Unauthorized",
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            status_code=401,
            detail=detail,
            code="UNAUTHORIZED",
            cause=cause,
        )


class ForbiddenError(HTTPError):
    """403 Forbidden."""

    _code: str = "QK_ERR_WEB_006"

    def __init__(
        self,
        detail: str = "Forbidden",
        cause: Exception | None = None,
    ) -> None:
        super().__init__(status_code=403, detail=detail, code="FORBIDDEN", cause=cause)


class MethodNotAllowedError(HTTPError):
    """405 Method Not Allowed."""

    _code: str = "QK_ERR_WEB_007"

    def __init__(
        self,
        detail: str = "Method Not Allowed",
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            status_code=405,
            detail=detail,
            code="METHOD_NOT_ALLOWED",
            cause=cause,
        )


class ConflictError(HTTPError):
    """409 Conflict."""

    _code: str = "QK_ERR_WEB_008"

    def __init__(
        self,
        detail: str = "Conflict",
        cause: Exception | None = None,
    ) -> None:
        super().__init__(status_code=409, detail=detail, code="CONFLICT", cause=cause)


class UnprocessableEntityError(HTTPError):
    """422 Unprocessable Entity."""

    _code: str = "QK_ERR_WEB_009"

    def __init__(
        self,
        detail: str = "Unprocessable Entity",
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            status_code=422,
            detail=detail,
            code="UNPROCESSABLE_ENTITY",
            cause=cause,
        )


class InternalServerError(HTTPError):
    """500 Internal Server Error."""

    _code: str = "QK_ERR_WEB_010"

    def __init__(
        self,
        detail: str = "Internal Server Error",
        code: str = "INTERNAL_SERVER_ERROR",
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            status_code=500,
            detail=detail,
            code=code,
            cause=cause,
        )


class DependencyResolutionError(InternalServerError):
    """500 Dependency Resolution Error."""

    _code: str = "QK_ERR_WEB_011"

    def __init__(
        self,
        param: str,
        service_type: Any,
        cause: Exception | None = None,
    ) -> None:
        self.param = param
        self.service_type = service_type
        super().__init__(
            detail=f"Failed to resolve dependency for parameter '{param}'",
            code="dependency_resolution_error",
            cause=cause,
        )
        self.details.update({"param": param, "service_type": str(service_type)})


class RateLimitError(HTTPError):
    """429 Too Many Requests."""

    _code: str = "QK_ERR_WEB_012"

    def __init__(
        self,
        detail: str = "Too Many Requests",
        retry_after: int | None = None,
        cause: Exception | None = None,
    ) -> None:
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(
            status_code=429,
            detail=detail,
            headers=headers,
            code="RATE_LIMIT_EXCEEDED",
            cause=cause,
        )


class TooManyConnectionsError(HTTPError):
    """503 Service Unavailable — connection limit reached.

    Raised when a streaming endpoint (e.g. SSE) has reached its
    ``max_connections`` cap and cannot accept further connections.
    """

    _code: str = "QK_ERR_WEB_013"

    def __init__(
        self,
        detail: str = "Too many active connections",
        cause: Exception | None = None,
    ) -> None:
        super().__init__(
            status_code=503,
            detail=detail,
            code="TOO_MANY_CONNECTIONS",
            cause=cause,
        )


__all__ = [
    "BadRequestError",
    "ConflictError",
    "DependencyResolutionError",
    "ForbiddenError",
    "HTTPError",
    "InternalServerError",
    "MethodNotAllowedError",
    "NotFoundError",
    "RateLimitError",
    "TooManyConnectionsError",
    "UnauthorizedError",
    "UnprocessableEntityError",
]
