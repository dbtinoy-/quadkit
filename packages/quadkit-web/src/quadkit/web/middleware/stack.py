"""Default middleware stack for Quadkit Web.

Provides :class:`DefaultMiddlewareStack` — an explicit, named class that
encapsulates the minimum set of Starlette-compatible middlewares applied by
every Quadkit web application.

Users can import this class to inspect, extend, or reproduce the default
middleware stack without relying on opaque ``WebProvider`` internals.
``WebProvider`` uses this class internally for DRY consistency.

Example::

    from quadkit.web.middleware import DefaultMiddlewareStack

    stack = DefaultMiddlewareStack(container=container)
    middlewares = stack.build()
    # pass to Starlette(middleware=middlewares, ...)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from starlette.middleware import Middleware as StarletteMiddleware
    from starlette.types import ASGIApp

    from quadkit.contracts.core.di import ContainerResolverProtocol

logger = get_logger(__name__)


class DefaultMiddlewareStack:
    """Builds the default Quadkit middleware stack as an explicit, composable list.

    Encapsulates the minimum set of middlewares that every Quadkit web
    application applies so users can see and extend it without magic.

    :class:`~quadkit.web.di.provider.WebProvider` delegates to this class
    internally, ensuring that all code paths produce the same default stack.

    Args:
        container: The resolved DI container.  Required for
            :class:`~quadkit.web.middleware.di_scope.DIScopeMiddleware` which
            provides request-scoped dependency resolution.
        extra_middlewares: Additional user-supplied Quadkit middlewares to
            include in the stack.  They are adapted to Starlette
            ``Middleware`` wrappers via
            :class:`~quadkit.web.middleware.registry.MiddlewareAdapterRegistry`
            and follow ``DIScopeMiddleware`` in user-supplied order — the
            DI-scope layer always stays outermost so request-scoped
            resolution is available to every later layer.

    Example::

        from quadkit.web.middleware import DefaultMiddlewareStack
        from quadkit.logging import get_logger

        logger = get_logger(__name__)

        # Inspect the default stack
        stack = DefaultMiddlewareStack(container=container)
        for mw in stack.build():
            logger.debug("middleware", name=mw.cls.__name__)

        # Extend with custom middleware
        stack = DefaultMiddlewareStack(
            container=container,
            extra_middlewares=[MyTimingMiddleware()],
        )
    """

    def __init__(
        self,
        container: ContainerResolverProtocol | None = None,
        extra_middlewares: list[Any] | None = None,
    ) -> None:
        """Initialise the stack builder.

        Args:
            container: Resolved DI container for ``DIScopeMiddleware``.
            extra_middlewares: Optional extra Quadkit middlewares to include.
        """
        self._container = container
        self._extra_middlewares: list[Any] = list(extra_middlewares or [])

    def build(self) -> list[StarletteMiddleware]:
        """Build and return the ordered list of default Starlette middlewares.

        The always-present entry is
        :class:`~quadkit.web.middleware.di_scope.DIScopeMiddleware`.
        Any ``extra_middlewares`` supplied at construction time are prepended
        to that entry after adaptation.

        Returns:
            An ordered list of :class:`starlette.middleware.Middleware`
            instances ready to pass to
            :class:`starlette.applications.Starlette`.
        """
        from typing import cast

        from quadkit.web.middleware.di_scope import DIScopeMiddleware
        from quadkit.web.middleware.registry import MiddlewareAdapterRegistry

        registry = MiddlewareAdapterRegistry.with_defaults()

        # Start from user-supplied extras (order preserved)
        middlewares: list[Any] = list(self._extra_middlewares)

        # Always ensure DIScopeMiddleware is present for request-scoped DI
        has_scope_mw = any(isinstance(mw, DIScopeMiddleware) for mw in middlewares)
        if not has_scope_mw and self._container is not None:
            middlewares.insert(
                0,
                DIScopeMiddleware(cast("ASGIApp", None), self._container),  # type: ignore[arg-type]
            )
            logger.debug("default_middleware_stack.added_di_scope")

        adapted = [registry.adapt(mw) for mw in middlewares]
        logger.debug("default_middleware_stack.built", count=len(adapted))
        return adapted


__all__ = ["DefaultMiddlewareStack"]
