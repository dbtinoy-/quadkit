"""DI middleware — per-request container scoping."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.middleware.types import NextHandler

logger = get_logger(__name__)


class ScopedMiddleware:
    """Middleware that creates a fresh DI scope for each invocation.

    A new child scope is opened before the downstream handler is called and
    automatically disposed when the handler returns (or raises).  The active
    scope is attached to the context as ``_scope`` so that nested resolvers
    can use it for request-scoped dependency resolution.

    The ``container`` argument **must** satisfy the container protocol from
    :mod:`quadkit.contracts.core.di` — specifically it must expose an
    async ``scope()`` context manager that yields a child
    :class:`~quadkit.contracts.core.di.ContainerResolverProtocol`.  Passing a
    plain object that does not implement ``scope()`` will raise
    :exc:`AttributeError` at call time.

    Use :class:`~quadkit.di.container.Container` (from the ``quadkit``
    package) as the canonical implementation.  Never pass the container itself
    into business-logic services resolved within the scope — use constructor
    injection instead.

    Args:
        container: A DI container that implements the ``scope()`` async
            context-manager protocol (see
            :class:`~quadkit.contracts.core.di.ContainerRegistrarProtocol`).

    Example:
        ```python
        from quadkit.middleware import ScopedMiddleware
        from quadkit.middleware.core.chain import MiddlewareChain

        chain = MiddlewareChain([ScopedMiddleware(container)])
        result = await chain.execute(context, handler)
        ```
    """

    __slots__ = ("_container",)

    def __init__(self, container: Any) -> None:
        self._container = container

    async def __call__(self, context: Any, next_handler: NextHandler) -> Any:
        """Open a DI scope, run handler, then dispose the scope."""
        async with self._container.scope() as scope:
            try:
                context._scope = scope
            except (AttributeError, TypeError):
                logger.debug(
                    "scope_context_attach_failed", context_type=type(context).__name__
                )
            return await next_handler(context)


__all__ = ["ScopedMiddleware"]
