"""Middleware protocols for Quadkit Framework.

This module defines the universal middleware contract that is
transport-agnostic and can be adapted to ASGI, WSGI, or other transports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Coroutine

T = TypeVar("T")
TContext = TypeVar("TContext")
TResult = TypeVar("TResult")


@runtime_checkable
class MiddlewareProtocol(Protocol[TContext, TResult]):
    """Universal middleware contract.

    Middleware wraps async operations with cross-cutting concerns
    (logging, metrics, security, etc.). This protocol is transport-agnostic.

    Example:
        ```python
        class LoggingMiddleware(MiddlewareProtocol[dict[str, Any], Any]):
            async def __call__(
                self,
                context: dict[str, Any],
                next: Callable[[dict[str, Any]], Awaitable[Any]]
            ) -> Any:
                print(f"Before: {context}")
                result = await next(context)
                print(f"After: {result}")
                return result
        ```
    """

    async def __call__(
        self,
        context: TContext,
        next: Callable[[TContext], Awaitable[TResult]],
    ) -> TResult:
        """Process the context and call the next middleware/handler.

        Args:
            context: Arbitrary context (dict, request, scope, etc.)
            next: Callable to invoke the next middleware or handler

        Returns:
            TResult: Result from the next middleware/handler
        """
        ...


Middleware = MiddlewareProtocol[dict[str, Any], Any]


@runtime_checkable
class ExceptionFilterChainProtocol(Protocol):
    """Protocol for exception filter chains."""

    def add(self, filter_: Any) -> ExceptionFilterChainProtocol:
        """Add a filter to the chain.

        Args:
            filter_: The filter to add (should satisfy ExceptionFilterProtocol protocol).

        Returns:
            The filter chain for fluent chaining.
        """
        ...

    async def handle(
        self,
        exc: Exception,
        request: Any,
        fallback: Callable[..., Any] | None = None,
    ) -> Any:
        """Handle an exception by passing it through the chain.

        Args:
            exc: The exception to handle.
            request: The request context.
            fallback: Optional fallback handler.

        Returns:
            The result of the filter chain (e.g. a Response object).
        """
        ...


@runtime_checkable
class MiddlewarePipelineProtocol(Protocol):
    """Protocol for an immutable, composable middleware pipeline.

    Middleware pipelines chain ``async (context, next_handler) -> result``
    callables so that each middleware wraps the next.  Implementations must
    be immutable — ``add`` returns a **new** pipeline rather than mutating
    the existing one.

    Example:
        ```python
        pipeline = MiddlewarePipeline()
        pipeline = pipeline.add(LoggingMiddleware())
        pipeline = pipeline.add(MetricsMiddleware())
        result = await pipeline.execute(context, handler)
        ```
    """

    def add(self, middleware: Any) -> MiddlewarePipelineProtocol:
        """Return a new pipeline with *middleware* appended.

        Args:
            middleware: An ``async (context, next_handler) -> result`` callable.

        Returns:
            A new pipeline with the middleware added.
        """
        ...

    async def execute(
        self,
        context: Any,
        handler: Callable[..., Coroutine[Any, Any, Any]],
    ) -> Any:
        """Execute the pipeline, passing *context* through all middleware.

        Args:
            context: The request/context object to process.
            handler: The final ``async (context) -> result`` handler at the
                end of the chain.

        Returns:
            The result from the handler (possibly transformed by middleware).
        """
        ...

    def __len__(self) -> int:
        """Return the number of middleware in the pipeline."""
        ...


__all__ = [
    "ExceptionFilterChainProtocol",
    "Middleware",
    "MiddlewarePipelineProtocol",
    "MiddlewareProtocol",
]
