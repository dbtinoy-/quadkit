"""Base middleware infrastructure.

Provides the foundation for building middleware pipelines.
"""

# Mypy struggles to fully resolve nested generics in middleware pipelines; allow
# targeted suppression in this module where we use casts.
# mypy: disable-error-code = no-any-return

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any, Generic, TypeVar

from quadkit.events.messages.base import Message

TMessage = TypeVar("TMessage", bound=Message)
TResult = TypeVar("TResult")

# Type for the next handler in the pipeline
NextHandler = Callable[[TMessage], Awaitable[TResult]]


class AbstractMiddleware(ABC, Generic[TMessage, TResult]):
    """Abstract base for middleware components.

    Middleware wraps around handlers to add cross-cutting concerns
    like logging, validation, transactions, etc.

    Example:
        ```python
        class TimingMiddleware(AbstractMiddleware[Message, Any]):
            async def __call__(
                self,
                message: Message,
                next_handler: NextHandler
            ) -> Any:
                start = time.time()
                result = await next_handler(message)
                duration = time.time() - start
                logger.info("Handler took %.3fs", duration)
                return result
        ```
    """

    @abstractmethod
    async def __call__(self, message: TMessage, next_handler: NextHandler) -> TResult:
        """Process the message and call the next handler.

        Args:
            message: The message being processed
            next_handler: The next handler in the pipeline

        Returns:
            Handler result
        """
        ...


class MiddlewareChain(Generic[TMessage, TResult]):
    """Chain of middleware components.

    Builds and executes a middleware pipeline.

    Example:
        ```python
        chain = MiddlewareChain()
        chain.add(LoggingMiddleware())
        chain.add(ValidationMiddleware())
        chain.add(TransactionMiddleware())

        result = await chain.execute(command, final_handler)
        ```
    """

    def __init__(self) -> None:
        """Initialize the middleware chain."""
        self._middlewares: list[AbstractMiddleware[TMessage, TResult]] = []

    def add(
        self,
        middleware: AbstractMiddleware[TMessage, TResult],
    ) -> MiddlewareChain[TMessage, TResult]:
        """Add middleware to the chain.

        Args:
            middleware: Middleware to add

        Returns:
            Self for chaining
        """
        self._middlewares.append(middleware)
        return self

    def insert(
        self,
        index: int,
        middleware: AbstractMiddleware[TMessage, TResult],
    ) -> MiddlewareChain[TMessage, TResult]:
        """Insert middleware at a specific position.

        Args:
            index: Position to insert at
            middleware: Middleware to insert

        Returns:
            Self for chaining
        """
        self._middlewares.insert(index, middleware)
        return self

    def clear(self) -> None:
        """Clear all middleware."""
        self._middlewares.clear()

    async def execute(
        self,
        message: TMessage,
        final_handler: Callable[[TMessage], Awaitable[TResult]],
    ) -> TResult:
        """Execute the middleware chain.

        Args:
            message: The message to process
            final_handler: The final handler to call

        Returns:
            Handler result
        """
        if not self._middlewares:
            from typing import cast

            return await self._call_handler(final_handler, message)

        # Build the chain from the end
        async def build_chain(index: int) -> Callable[[TMessage], Awaitable[TResult]]:
            if index >= len(self._middlewares):
                return lambda msg: self._call_handler(final_handler, msg)

            middleware = self._middlewares[index]
            from typing import cast

            next_handler = await build_chain(index + 1)

            async def handler(msg: TMessage) -> TResult:
                # Call the middleware's __call__ method directly.
                # It is defined to be async.
                res: Awaitable[TResult] = middleware.__call__(msg, next_handler)
                # Cast through Any to prevent mypy from resolving complex generics
                return cast("TResult", await cast("Awaitable[Any]", res))

            return cast("Callable[[TMessage], Awaitable[TResult]]", handler)

        chain = await build_chain(0)
        from typing import cast

        # Execute chain and cast result explicitly
        res: Any = await chain(message)
        return cast("TResult", res)

    async def _call_handler(self, handler: Any, message: TMessage) -> TResult:
        """Call the handler."""
        import asyncio
        from typing import cast

        if callable(handler) and not hasattr(handler, "handle"):
            result = handler(message)
        elif hasattr(handler, "handle"):
            result = handler.handle(message)
        else:
            raise TypeError(f"Invalid handler: {type(handler)}")

        if asyncio.iscoroutine(result):
            return await result
        # Explicitly cast to TResult to satisfy static analysis
        return cast("TResult", result)


# Function-based middleware helper
def middleware(func: Callable) -> AbstractMiddleware:
    """Decorator to create middleware from a function.

    Example:
        ```python
        @middleware
        async def my_middleware(message, next_handler):
            # Pre-processing
            result = await next_handler(message)
            # Post-processing
            return result
        ```
    """

    class FunctionMiddleware(AbstractMiddleware):
        async def __call__(self, message: Any, next_handler: Any) -> Any:
            return await func(message, next_handler)

    return FunctionMiddleware()


__all__ = ["AbstractMiddleware", "MiddlewareChain", "NextHandler", "middleware"]
