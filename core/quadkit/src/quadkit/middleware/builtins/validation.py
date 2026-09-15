"""Validation middleware — input validation and error handling."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.middleware.types import NextHandler

logger = get_logger(__name__)


class ErrorHandlerMiddleware:
    """Middleware that catches exceptions and optionally transforms them.

    Catches only the explicitly specified exception types.
    Can be configured with a custom error handler or a fallback value.

    Args:
        catch: Exception types to catch. Must be explicitly provided.
        fallback: Value to return when an exception is caught and no
            error_handler is provided.
        error_handler: Optional callable ``(exception, context) -> result``
            to handle errors. If it returns ``None``, the exception is re-raised.
    """

    __slots__ = ("_catch", "_error_handler", "_fallback")

    def __init__(
        self,
        catch: type[Exception] | tuple[type[Exception], ...],
        fallback: Any = None,
        error_handler: Any = None,
    ) -> None:
        # Validate that catch contains only Exception subclasses
        catch_types = (catch,) if isinstance(catch, type) else catch
        for exc_type in catch_types:
            assert issubclass(exc_type, Exception), (  # noqa: S101  # config-time guard
                f"catch must contain only Exception subclasses; got {exc_type!r}"
            )

        self._fallback = fallback
        self._error_handler = error_handler
        self._catch = catch

    async def __call__(self, context: Any, next_handler: NextHandler) -> Any:
        """Catch exceptions and optionally invoke the error handler."""
        try:
            return await next_handler(context)
        except self._catch as e:
            if self._error_handler is not None:
                result = self._error_handler(e, context)
                if inspect.isawaitable(result):
                    result = await result
                if result is not None:
                    return result
                raise
            logger.exception(
                "middleware_error_handled",
                error_type=type(e).__name__,
                error=str(e),
            )
            return self._fallback


class ValidationMiddleware:
    """Middleware that validates the context before proceeding.

    Accepts a sync or async validator callable that should raise on
    invalid input. The middleware calls the validator and, if it
    passes, delegates to the next handler.

    Args:
        validator: A callable ``(context) -> None`` that raises on
            invalid input.
    """

    __slots__ = ("_validator",)

    def __init__(self, validator: Any) -> None:
        self._validator = validator

    async def __call__(self, context: Any, next_handler: NextHandler) -> Any:
        """Validate context, then proceed to next handler."""
        result = self._validator(context)
        if inspect.isawaitable(result):
            await result
        return await next_handler(context)


__all__ = ["ErrorHandlerMiddleware", "ValidationMiddleware"]
