"""Routing middleware — conditional middleware application."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.core.middleware import MiddlewareProtocol
    from quadkit.middleware.types import NextHandler


class ConditionalMiddleware:
    """Apply wrapped middleware only when predicate returns True for context."""

    __slots__ = ("_middleware", "_name", "_predicate")

    def __init__(
        self,
        middleware: MiddlewareProtocol[Any, Any],
        predicate: Callable[[Any], bool],
        *,
        name: str = "conditional",
    ) -> None:
        self._middleware = middleware
        self._predicate = predicate
        self._name = name

    async def __call__(self, context: Any, next_handler: NextHandler) -> Any:
        if self._predicate(context):
            return await self._middleware(context, next_handler)
        return await next_handler(context)


__all__ = ["ConditionalMiddleware"]
