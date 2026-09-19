"""Exception filter chain for handling and transforming exceptions.

This module provides an immutable exception filter chain that can be
registered and invoked to convert exceptions into appropriate responses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.web.protocols import ExceptionFilterProtocol

logger = get_logger(__name__)


class ExceptionFilterChain:
    """Immutable chain of exception filters for handling errors.

    Exception filters convert exceptions to appropriate responses based on
    exception type. The chain is immutable - each ``add`` returns a new chain.

    Example::

        from quadkit.middleware.core.exception_filters import ExceptionFilterChain

        chain = (
            ExceptionFilterChain()
            .add(ValidationExceptionFilter())
            .add(NotFoundExceptionFilter())
            .add(CatchAllExceptionFilter())
        )

        response = await chain.handle(exc, request)
    """

    __slots__ = ("_filters",)

    def __init__(self, filters: list[ExceptionFilterProtocol] | None = None) -> None:
        """Initialize the filter chain.

        Args:
            filters: Optional list of exception filters.
        """
        self._filters: list[ExceptionFilterProtocol] = list(filters) if filters else []

    def add(self, filter_: ExceptionFilterProtocol) -> ExceptionFilterChain:
        """Return a new chain with the filter appended.

        Args:
            filter_: An exception filter implementing ExceptionFilterProtocol protocol.

        Returns:
            A new ``ExceptionFilterChain`` with the filter added.
        """
        return ExceptionFilterChain([*self._filters, filter_])

    async def handle(
        self,
        exc: Exception,
        request: Any,
        fallback: Callable[[Exception, Any], Any] | None = None,
    ) -> Any:
        """Process the exception through all filters.

        Iterates through filters in order and uses the first one that
        ``can_handle`` the exception.

        Args:
            exc: The exception to handle.
            request: The original request context.
            fallback: Optional fallback handler if no filter matches.

        Returns:
            The response from the first matching filter, or the result
            of the fallback handler, or re-raises the exception.

        Raises:
            Exception: If no filter handles the exception and no fallback
                is provided.
        """
        for filter_ in self._filters:
            try:
                if filter_.can_handle(exc):
                    logger.debug(
                        "exception_handled",
                        filter_type=type(filter_).__name__,
                        exc_type=type(exc).__name__,
                    )
                    return filter_.handle(exc, request)
            except Exception as filter_err:  # filter error boundary: filter failure must not hide the original exception
                logger.error(
                    "exception_filter_failed",
                    filter_type=type(filter_).__name__,
                    exc_type=type(exc).__name__,
                    error=str(filter_err),
                )
                raise

        if fallback is not None:
            logger.debug(
                "exception_fallback",
                exc_type=type(exc).__name__,
            )
            return fallback(exc, request)

        logger.warning(
            "exception_unhandled",
            exc_type=type(exc).__name__,
            filter_count=len(self._filters),
        )
        raise exc

    def find_handler(self, exc: Exception) -> ExceptionFilterProtocol | None:
        """Find the first filter that can handle the exception.

        Args:
            exc: The exception to check.

        Returns:
            The first matching filter, or None if no filter can handle it.
        """
        for filter_ in self._filters:
            if filter_.can_handle(exc):
                return filter_
        return None

    def __len__(self) -> int:
        """Return the number of filters in the chain."""
        return len(self._filters)

    def __repr__(self) -> str:
        return f"ExceptionFilterChain({len(self._filters)} filters)"


class ValidationExceptionFilter:
    """Catch ValidationError, return structured 422 response."""

    __slots__ = ()

    def can_handle(self, exc: Exception) -> bool:
        from quadkit.contracts.exceptions.domain import ValidationError

        return isinstance(exc, ValidationError)

    def handle(self, exc: Exception, request: Any) -> dict[str, Any]:
        return {"error": "validation_error", "details": str(exc), "status": 422}


class NotFoundExceptionFilter:
    """Catch NotFoundError, return structured 404 response."""

    __slots__ = ()

    def can_handle(self, exc: Exception) -> bool:
        from quadkit.contracts.exceptions.domain import NotFoundError

        return isinstance(exc, NotFoundError)

    def handle(self, exc: Exception, request: Any) -> dict[str, Any]:
        return {"error": "not_found", "details": str(exc), "status": 404}


class InfrastructureExceptionFilter:
    """Catch InfrastructureError, log at error level, return 500 response."""

    __slots__ = ()

    def can_handle(self, exc: Exception) -> bool:
        from quadkit.contracts.exceptions.infra import InfrastructureError

        return isinstance(exc, InfrastructureError)

    def handle(self, exc: Exception, request: Any) -> dict[str, Any]:
        logger.error("infrastructure_error", error=str(exc), exc_info=exc)
        return {"error": "internal_error", "status": 500}


class MiddlewarePolicyExceptionFilter:
    """Catch policy-level middleware errors, return appropriate status codes.

    Handles MiddlewareAuthError (401), MiddlewareRateLimitError (429),
    and other MiddlewarePolicyError exceptions (403).
    """

    __slots__ = ()

    def can_handle(self, exc: Exception) -> bool:
        from quadkit.middleware.exceptions import MiddlewarePolicyError

        return isinstance(exc, MiddlewarePolicyError)

    def handle(self, exc: Exception, request: Any) -> dict[str, Any]:
        from quadkit.middleware.exceptions import (
            MiddlewareAuthError,
            MiddlewareRateLimitError,
        )

        if isinstance(exc, MiddlewareAuthError):
            return {"error": "unauthorized", "status": 401}
        if isinstance(exc, MiddlewareRateLimitError):
            return {"error": "rate_limit_exceeded", "status": 429}
        return {"error": getattr(exc, "_code", "POLICY_ERROR"), "status": 403}


__all__ = [
    "ExceptionFilterChain",
    "InfrastructureExceptionFilter",
    "MiddlewarePolicyExceptionFilter",
    "NotFoundExceptionFilter",
    "ValidationExceptionFilter",
]
