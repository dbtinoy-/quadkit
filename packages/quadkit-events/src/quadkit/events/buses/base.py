"""Base bus infrastructure with middleware support.

This module provides the foundation for all message buses including:
- Middleware pipeline execution
- Explicit handler registration (no service locator)
- Handler resolution from registered handlers only

WARNING: Buses do NOT accept a DI container reference. Handlers must
be explicitly registered via ``bus.register()`` or through the
``HandlerRegistry.register_with_buses()`` method during the provider's
``register()`` phase. This eliminates the service locator anti-pattern
(F-006) and ensures full testability without a container.
"""

# Mypy struggles to fully resolve nested generic middleware chains; add a
# targeted suppression for 'no-any-return' where we perform casts to bridge
# runtime and static typing.
# mypy: disable-error-code = no-any-return

from __future__ import annotations

from abc import ABC
import asyncio
from collections.abc import Awaitable, Callable
from typing import (
    Any,
    Generic,
    Protocol,
    TypeVar,
)

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.events.exceptions import HandlerNotFoundError
from quadkit.events.messages.base import Message
from quadkit.logging import get_logger

logger = get_logger(__name__)

# Type variables
TMessage = TypeVar("TMessage", bound=Message)
TResult = TypeVar("TResult")

# Middleware type alias
MiddlewareFunc = Callable[
    [TMessage, Callable[[TMessage], Awaitable[TResult]]],
    Awaitable[TResult],
]


class HandlerLike(Protocol):
    """Structural type for handler objects exposing a ``handle`` method.

    Buses accept three handler shapes: plain callables, handler classes
    (instantiated by the bus), and pre-built handler objects. The concrete
    bus pins the message type (e.g. ``Bus[Command, Any]``), so the protocol
    stays loose about the handled message.
    """

    def handle(self, message: Any) -> Any: ...


class Bus(ABC, Generic[TMessage, TResult]):
    """Abstract base for message buses.

    All buses support:
    - Middleware pipelines
    - Explicit handler registration via ``register()``

    Handlers are resolved exclusively from the internal ``_handlers`` dict.
    There is no container-based fallback — all wiring must happen at
    construction or registration time.

    Attributes:
        _middlewares: List of middleware functions.
        _handlers: Dictionary mapping message types to handlers.
    """

    def __init__(
        self,
        middlewares: list[MiddlewareFunc] | None = None,
    ) -> None:
        """Initialize the bus.

        Args:
            middlewares: List of middleware functions.
        """
        self._middlewares: list[MiddlewareFunc] = middlewares or []
        self._handlers: dict[type[TMessage], Any] = {}

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Report readiness for a process-local bus with no external probe."""
        _ = timeout
        return HealthCheckResult(
            component=self.__class__.__name__,
            status=HealthStatus.HEALTHY,
            details={
                "handler_count": len(self._handlers),
                "middleware_count": len(self._middlewares),
            },
        )

    def register(
        self,
        message_type: type[TMessage],
        handler: Callable[[TMessage], Any] | type | HandlerLike,
    ) -> None:
        """Register a handler for a message type.

        Args:
            message_type: The message class to handle.
            handler: Handler function, handler class, or handler object
                with a ``handle(message)`` method.
        """
        self._handlers[message_type] = handler

    def use(self, middleware: MiddlewareFunc) -> Bus[TMessage, TResult]:
        """Add middleware to the pipeline.

        Args:
            middleware: Middleware function.

        Returns:
            Self for chaining.
        """
        self._middlewares.append(middleware)
        return self

    async def _resolve_handler(self, message_type: type[TMessage]) -> Any:
        """Resolve handler for a message type.

        Resolution checks only explicitly registered handlers.
        No container fallback — this eliminates the service locator pattern.

        Args:
            message_type: The message class.

        Returns:
            The resolved handler.

        Raises:
            HandlerNotFoundError: If no handler found.
        """
        if message_type in self._handlers:
            handler = self._handlers[message_type]
            # If handler is a class, instantiate it
            if isinstance(handler, type):
                return handler()
            return handler

        raise HandlerNotFoundError("Handler", message_type.__name__)

    async def _execute_pipeline(
        self,
        message: TMessage,
        final_handler: Callable[[TMessage], TResult],
    ) -> TResult:
        """Execute message through middleware pipeline.

        Args:
            message: The message to process.
            final_handler: The actual handler at the end of the pipeline.

        Returns:
            Handler result.
        """
        if not self._middlewares:
            from typing import cast

            return cast(
                "TResult",
                await cast("Any", self._call_handler(final_handler, message)),
            )

        # Build middleware chain
        async def chain(idx: int, msg: TMessage) -> TResult:
            if idx >= len(self._middlewares):
                from typing import cast

                return cast(
                    "TResult",
                    await cast("Any", self._call_handler(final_handler, msg)),
                )

            middleware = self._middlewares[idx]
            mw = middleware

            def _next(m: TMessage) -> Awaitable[TResult]:
                return chain(idx + 1, m)

            res: Awaitable[TResult] = mw(msg, _next)
            return await res

        return await chain(0, message)

    async def _call_handler(self, handler: Any, message: TMessage) -> TResult:
        """Call handler with message.

        Supports both function handlers and class handlers with handle() method.

        Args:
            handler: The handler to call.
            message: The message to handle.

        Returns:
            Handler result.
        """
        # If handler is callable (function or callable object)
        from typing import cast

        if callable(handler):
            result = handler(message)
            if asyncio.iscoroutine(result):
                return await result
            return cast("TResult", result)

        # If handler is object with handle method
        if hasattr(handler, "handle"):
            result = handler.handle(message)
            if asyncio.iscoroutine(result):
                result = await result
            # If the handler returned Result[None, E] and it is Err, raise the
            # error so the bus retry/error-handling logic can process it.
            if hasattr(result, "is_err") and result.is_err():
                raise result.unwrap_err()
            return cast("TResult", result)

        raise TypeError(f"Invalid handler type: {type(handler)}")


__all__ = ["Bus", "MiddlewareFunc"]
