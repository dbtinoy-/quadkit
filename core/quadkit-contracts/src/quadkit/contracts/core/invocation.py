"""Transport-neutral invocation protocols.

These protocols decouple the kernel invocation machinery from any specific
transport (HTTP, WebSocket, CLI, etc.) and are the foundation for Phase 3
transport decoupling.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class InvocationContextProtocol(Protocol):
    """Transport-neutral invocation context.

    Represents the minimal shared surface of any invocation context —
    whether it originates from HTTP, a CLI command, a background task, etc.
    Concrete transports extend this with their own typed attributes.
    """


@runtime_checkable
class InvocationHandlerProtocol(Protocol):
    """Transport-neutral handler protocol.

    A handler receives an invocation context and produces a result.
    Implementations are responsible for executing the underlying business
    logic associated with an invocation.
    """

    async def handle(self, context: Any) -> Any:
        """Execute the handler for the given context.

        Args:
            context: The invocation context (typed per transport).

        Returns:
            The result of handler execution.
        """
        ...


@runtime_checkable
class InvocationMiddlewareProtocol(Protocol):
    """Transport-neutral middleware protocol.

    Middleware wraps handler execution with cross-cutting concerns such as
    logging, metrics, authentication, or tracing.  Each middleware calls
    ``next_handler`` to continue the chain.
    """

    async def __call__(self, context: Any, next_handler: Any) -> Any:
        """Process the context and delegate to the next handler.

        Args:
            context: The invocation context.
            next_handler: Callable representing the remainder of the chain.

        Returns:
            The result from the next handler (possibly transformed).
        """
        ...


@runtime_checkable
class InvocationPipelineProtocol(Protocol):
    """Transport-neutral pipeline protocol.

    An immutable, composable pipeline of ``InvocationMiddlewareProtocol``
    instances.  ``add`` must return a **new** pipeline rather than mutating
    the existing one.

    Example::

        pipeline = MyPipeline()
        pipeline = pipeline.add(LoggingMiddleware())
        pipeline = pipeline.add(TracingMiddleware())
        result = await pipeline.execute(context, handler)
    """

    def add(self, middleware: Any) -> InvocationPipelineProtocol:
        """Return a new pipeline with *middleware* appended.

        Args:
            middleware: An invocation middleware instance.

        Returns:
            A new pipeline with the middleware added.
        """
        ...

    async def execute(self, context: Any, handler: Any) -> Any:
        """Execute the pipeline with the given context and terminal handler.

        Args:
            context: The invocation context.
            handler: The terminal handler called after all middleware.

        Returns:
            The result produced by the terminal handler (possibly
            transformed by middleware).
        """
        ...


__all__ = [
    "InvocationContextProtocol",
    "InvocationHandlerProtocol",
    "InvocationMiddlewareProtocol",
    "InvocationPipelineProtocol",
]
