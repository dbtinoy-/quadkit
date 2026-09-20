"""Middleware base class and registry.

Canonical Middleware Pattern
----------------------------

There is **one** canonical way to write middleware in Quadkit:

.. code-block:: python

    class MyMiddleware:
        def __init__(self, app: ASGIApp) -> None:
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            # before
            await self.app(scope, receive, send)
            # after (e.g. modify headers via a send wrapper)

Register via ``WebProvider`` ``middleware`` kwarg or
``provider.middleware_manager.add()``.

For route-specific concerns, use guards and interceptors instead of middleware.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import IntEnum
from typing import Any

from starlette.types import ASGIApp

from quadkit.logging import get_logger

logger = get_logger(__name__)


class MiddlewarePriority(IntEnum):
    """Simple ordering for middleware registration.

    Lower value => higher precedence (executed earlier / outermost).
    """

    EARLY = 0
    NORMAL = 1
    LATE = 2


class MiddlewareChain:
    """Chain of middleware for sequential execution"""

    def __init__(self, middlewares: list[Any]):
        self.middlewares = middlewares

    async def process_request(self, request: Any) -> Any | None:
        """Process request through middleware chain"""
        for middleware in self.middlewares:
            response = await middleware.process_request(request)
            if response is not None:
                # Short-circuit the chain
                return response
        return None

    async def process_response(self, response: Any) -> Any:
        """Process response through middleware chain (in reverse order)"""
        for middleware in reversed(self.middlewares):
            response = await middleware.process_response(response)
        return response


class MiddlewareRegistry:
    """Registry to track and prevent duplicate middleware.

    Ensures each middleware type is only registered once,
    preventing double-execution bugs.
    """

    def __init__(self) -> None:
        """Initialize middleware registry."""
        self._registered_types: set[type[Any]] = set()
        self._registered_names: set[str] = set()
        self._middleware_order: list[str] = []
        # Store tuples: (priority: int, middleware_class: Type, options: dict)
        self._middleware_stack: list[tuple[int, type[Any], dict]] = []
        # Cache for sorted middleware
        self._sorted_cache: list[tuple[int, type[Any], dict]] | None = None

    def register_middleware(
        self,
        middleware_class: type[Any],
        *,
        priority: MiddlewarePriority = MiddlewarePriority.NORMAL,
        **options: Any,
    ) -> None:
        """Register ASGI middleware class with duplicate checking and priority.

        Args:
            middleware_class: ASGI Middleware class to register
            priority: MiddlewarePriority (EARLY, NORMAL, LATE)
            options: Additional middleware options

        Raises:
            ValueError: If middleware already registered
        """
        # Check if already registered
        if middleware_class in self._registered_types:
            logger.warning(
                "Middleware %s already registered, skipping",
                middleware_class.__name__,
            )
            return

        # Invalidate cache when new middleware is added
        self._sorted_cache = None

        # Track registration
        self._registered_types.add(middleware_class)
        self._middleware_order.append(middleware_class.__name__)

        # Store middleware entry with its priority for later composition
        self._middleware_stack.append((int(priority), middleware_class, options))

        logger.info(
            "Registered middleware: %s (order: %d, priority: %s)",
            middleware_class.__name__,
            len(self._middleware_order),
            priority.name,
        )

    def compose_app(self, app: ASGIApp) -> ASGIApp:
        """Compose the middleware stack around the app.

        Uses cached sorted middleware for performance.

        Args:
            app: The base ASGI app

        Returns:
            App wrapped with all middleware
        """
        # Use cached sorted middleware if available
        if self._sorted_cache is None:
            # Order entries by priority (EARLY -> NORMAL -> LATE) so that when we
            # apply them in reverse we get outermost EARLY -> ... -> innermost LATE.
            self._sorted_cache = sorted(self._middleware_stack, key=lambda t: t[0])

        # Apply middleware in reverse order (innermost first)
        for _, middleware_class, options in reversed(self._sorted_cache):
            app = middleware_class(app, **options)

        return app

    def register_function_middleware(
        self,
        app: Any,
        func: Callable[..., Any],
        name: str | None = None,
    ) -> None:
        """Register function-based middleware with duplicate checking.

        Args:
            app: Starlette application
            func: Middleware function
            name: Unique name for this middleware (defaults to function name)

        Raises:
            ValueError: If middleware with same name already registered
        """
        middleware_name = name or func.__name__

        # Check if already registered
        if middleware_name in self._registered_names:
            logger.warning(
                "Function middleware '%s' already registered, skipping",
                middleware_name,
            )
            return

        # Register and track
        app.middleware("http")(func)
        self._registered_names.add(middleware_name)
        self._middleware_order.append(middleware_name)

        logger.info(
            "Registered function middleware: %s (order: %d)",
            middleware_name,
            len(self._middleware_order),
        )

    def get_middleware_order(self) -> list[str]:
        """Get list of registered middleware in execution order.

        Returns:
            List of middleware names in order they execute
        """
        return self._middleware_order.copy()

    def is_registered(
        self,
        middleware: type[Any] | str,
    ) -> bool:
        """Check if middleware is registered.

        Args:
            middleware: Middleware class or name

        Returns:
            True if middleware is registered
        """
        if isinstance(middleware, str):
            return middleware in self._registered_names
        return middleware in self._registered_types
