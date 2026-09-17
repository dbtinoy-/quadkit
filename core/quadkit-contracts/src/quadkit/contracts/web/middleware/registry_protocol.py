"""Web middleware registry protocol for cross-package middleware registration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

if True:
    Scope = dict[str, Any]
    Receive = Any
    Send = Any
    ASGIApp = Callable[[Scope, Receive, Send], Any]
    MiddlewareFactory = Callable[[ASGIApp], ASGIApp]


class MiddlewareRegistryProtocol(Protocol):
    """Protocol for registering ASGI middleware.

    This protocol defines the interface for middleware registration
    used by cross-package integrations like tenant context bridging.

    Supports two registration patterns:
    - Class-based: register_middleware(MyMiddlewareClass)
    - Factory-based: register_middleware_factory(lambda app: MyMiddleware(app))
    """

    def register_middleware(
        self,
        middleware_class: type[Any],
        *,
        priority: int = 0,
        **options: Any,
    ) -> None:
        """Register an ASGI middleware class.

        Args:
            middleware_class: ASGI middleware class to register.
            priority: Middleware priority (higher runs earlier).
            **options: Additional middleware options.
        """
        ...

    def register_middleware_factory(self, factory: MiddlewareFactory) -> None:
        """Register an ASGI middleware factory function.

        This is useful for cross-package integrations that need to
        wrap an app with middleware at registration time.

        Args:
            factory: A callable that takes an ASGI app and returns
                a wrapped ASGI app with middleware applied.
        """
        ...

    def get_middleware_stack(self) -> list[Callable[..., Any]]:
        """Get the registered middleware in composition order.

        Returns:
            List of middleware classes/factories.
        """
        ...


__all__ = ["MiddlewareRegistryProtocol"]
