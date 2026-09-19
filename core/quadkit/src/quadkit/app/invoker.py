"""Invoker — utility for invoking functions with DI and middleware."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar, cast

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from quadkit.contracts.core import MiddlewarePipelineProtocol
    from quadkit.di.container import Container

T = TypeVar("T")


class Invoker:
    """Invokes functions with dependency injection and middleware.

    This class decouples the invocation logic from the Application class,
    allowing it to be used in other contexts (like testing or custom runners).

    The ``context`` dict passed through the middleware pipeline satisfies
    :class:`~quadkit.contracts.core.invocation.InvocationContextProtocol` —
    a transport-neutral invocation context that transports can extend with
    typed attributes in Phase 3.
    """

    def __init__(
        self,
        container: Container,
        middleware: MiddlewarePipelineProtocol,
    ) -> None:
        self._container = container
        self._middleware = middleware
        # M-2: Unified invocation logic via FunctionInvoker
        self._invoker = container.create_invoker()

    async def invoke(
        self,
        func: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Invoke a function with automatic dependency injection and middleware.

        The invocation context passed through the middleware pipeline is a
        ``dict[str, Any]`` that structurally satisfies
        :class:`~quadkit.contracts.core.invocation.InvocationContextProtocol`.
        Middleware implementations should treat it as opaque and forward it
        unchanged unless they are deliberately enriching the context.
        """
        # Build the transport-neutral invocation context.
        # This dict is the runtime representation of InvocationContextProtocol
        # for the core (non-transport-specific) invocation path.
        context: dict[str, Any] = {
            "func": func,
            "args": args,
            "kwargs": kwargs,
        }

        async def _final_handler(_ctx: dict[str, Any] | None = None) -> T:
            return cast("T", await self._invoker.call(func, *args, **kwargs))

        return cast("T", await self._middleware.execute(context, _final_handler))
