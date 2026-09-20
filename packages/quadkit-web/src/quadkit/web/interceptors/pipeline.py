"""Interceptor pipeline for chaining interceptors.

The pipeline executes interceptors in order, passing control to the next
interceptor until the handler is reached.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.web.protocols import (
    CallHandlerProtocol,
    ExecutionContextProtocol,
    WebInterceptorProtocol,
)

if TYPE_CHECKING:
    from collections.abc import Callable


class DefaultCallHandler(CallHandlerProtocol):
    """Default call handler that executes the actual handler function."""

    def __init__(self, handler: Callable):
        """Initialize with the handler function.

        Args:
            handler: The actual handler function to call.
        """
        self._handler = handler

    async def handle(self) -> Any:
        """Execute the handler and return its result."""
        return await self._handler()


class InterceptorChain(CallHandlerProtocol):
    """Internal chain that links interceptors together."""

    def __init__(
        self,
        interceptors: list[WebInterceptorProtocol],
        index: int,
        final_handler: Callable,
        context: ExecutionContextProtocol,
    ):
        """Initialize the chain.

        Args:
            interceptors: List of interceptors to chain.
            index: Current index in the interceptor list.
            final_handler: The handler to call when all interceptors complete.
            context: The execution context.
        """
        self._interceptors = interceptors
        self._index = index
        self._final_handler = final_handler
        self._context = context

    async def handle(self) -> Any:
        """Execute the next interceptor or final handler."""
        if self._index >= len(self._interceptors):
            # All interceptors passed, execute final handler
            return await self._final_handler()

        # Get current interceptor and create next in chain
        interceptor = self._interceptors[self._index]
        next_chain = InterceptorChain(
            self._interceptors,
            self._index + 1,
            self._final_handler,
            self._context,
        )

        # Call the interceptor
        return await interceptor.intercept(self._context, next_chain)


class InterceptorPipeline:
    """Pipeline that manages and executes interceptors.

    Interceptors are executed in order, each having the opportunity to:
    - Execute code before the handler
    - Call the next interceptor/handler
    - Execute code after the handler (by transforming the result)
    - Short-circuit by returning early without calling next
    """

    def __init__(self, interceptors: list[WebInterceptorProtocol] | None = None):
        """Initialize the interceptor pipeline.

        Args:
            interceptors: Optional list of interceptors to register.
        """
        self._interceptors: list[WebInterceptorProtocol] = (
            list(interceptors) if interceptors else []
        )

    def add_interceptor(self, interceptor: WebInterceptorProtocol) -> None:
        """Add an interceptor to the pipeline.

        Interceptors are executed in the order they are added.

        Args:
            interceptor: The interceptor to add.
        """
        if interceptor not in self._interceptors:
            self._interceptors.append(interceptor)

    def remove_interceptor(self, interceptor: WebInterceptorProtocol) -> None:
        """Remove an interceptor from the pipeline.

        Args:
            interceptor: The interceptor to remove.
        """
        if interceptor in self._interceptors:
            self._interceptors.remove(interceptor)

    def clear(self) -> None:
        """Remove all interceptors from the pipeline."""
        self._interceptors.clear()

    @property
    def interceptors(self) -> list[WebInterceptorProtocol]:
        """Get the list of registered interceptors."""
        return list(self._interceptors)

    async def execute(
        self,
        context: ExecutionContextProtocol,
        handler: Callable,
    ) -> Any:
        """Execute the interceptor pipeline.

        Args:
            context: The execution context.
            handler: The final handler to execute.

        Returns:
            The result of the handler (possibly transformed by interceptors).
        """
        if not self._interceptors:
            # No interceptors, execute handler directly
            return await handler()

        # Create the chain starting with first interceptor
        chain = InterceptorChain(
            self._interceptors,
            0,
            handler,
            context,
        )

        return await chain.handle()

    def __len__(self) -> int:
        """Return the number of interceptors."""
        return len(self._interceptors)

    def __bool__(self) -> bool:
        """Return True if there are interceptors."""
        return bool(self._interceptors)


__all__ = ["DefaultCallHandler", "InterceptorChain", "InterceptorPipeline"]
