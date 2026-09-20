from __future__ import annotations

from typing import Any, TypeVar

from starlette import status
from starlette.requests import Request

from quadkit.logging import get_logger
from quadkit.web.exceptions import HTTPError

logger = get_logger(__name__)

T = TypeVar("T")


class RequestState:
    """Type-safe request state accessor."""

    @staticmethod
    def get(
        request: Request,
        key: str,
        type_: type[T],  # noqa: ARG004
        default: T | None = None,
    ) -> T | None:
        """Get value from request state with default.

        Args:
            request: The incoming HTTP request.
            key: State attribute name.
            type_: Expected return type (used for static analysis).
            default: Fallback when the attribute is absent.
        """
        return getattr(request.state, key, default)

    @staticmethod
    def require(
        request: Request,
        key: str,
        error_message: str | None = None,
    ) -> Any:
        """Get value from request state or raise HTTP 500."""
        if not hasattr(request.state, key):
            logger.error(
                "Required request state '%s' not set. Check middleware configuration.",
                key,
            )
            raise HTTPError(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_message or f"Internal error: {key} not initialized",
            )

        return getattr(request.state, key)

    @staticmethod
    def set(
        request: Request,
        key: str,
        value: Any,
    ) -> None:
        """Set value in request state."""
        setattr(request.state, key, value)
