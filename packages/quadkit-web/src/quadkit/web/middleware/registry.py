"""Middleware registry for quadkit-web.

Enables extensible adaptation of various middleware types (Starlette,
DIScope, Quadkit-native) into the final Starlette middleware stack.
"""

from __future__ import annotations

from typing import Any, Protocol, cast, runtime_checkable

from starlette.middleware import Middleware as StarletteMiddleware


@runtime_checkable
class _MiddlewareAdapterProtocol(Protocol):
    """Protocol for middleware adapters."""

    def can_adapt(self, middleware: Any) -> bool:
        """Return True if this adapter can handle the given middleware."""
        ...

    def adapt(self, middleware: Any) -> StarletteMiddleware:
        """Convert the middleware into a Starlette-compatible Middleware object."""
        ...


class _StarletteMiddlewareAdapter:
    """Handles native Starlette Middleware objects."""

    def can_adapt(self, middleware: Any) -> bool:
        return isinstance(middleware, StarletteMiddleware)

    def adapt(self, middleware: Any) -> StarletteMiddleware:
        return cast("StarletteMiddleware", middleware)


class _TupleMiddlewareAdapter:
    """Handles (MiddlewareClass, kwargs_dict) tuples."""

    def can_adapt(self, middleware: Any) -> bool:
        return isinstance(middleware, tuple) and len(middleware) >= 1

    def adapt(self, middleware: Any) -> StarletteMiddleware:
        if len(middleware) == 2 and isinstance(middleware[1], dict):
            return StarletteMiddleware(middleware[0], **middleware[1])
        # Positional args (deprecated)
        return StarletteMiddleware(middleware[0], *middleware[1:])


class _DIScopeMiddlewareAdapter:
    """Handles DIScopeMiddleware instances."""

    def can_adapt(self, middleware: Any) -> bool:
        # Check by class name to avoid direct dependency if possible
        return type(middleware).__name__ == "DIScopeMiddleware"

    def adapt(self, middleware: Any) -> StarletteMiddleware:
        return StarletteMiddleware(
            cast("Any", type(middleware)),
            container=getattr(middleware, "container", None),
        )


class _HTTPMiddlewareAdapterBase:
    """Handles Starlette BaseHTTPMiddleware instances."""

    def can_adapt(self, middleware: Any) -> bool:
        from starlette.middleware.base import BaseHTTPMiddleware

        return isinstance(middleware, BaseHTTPMiddleware)

    def adapt(self, middleware: Any) -> StarletteMiddleware:
        return StarletteMiddleware(
            cast("Any", type(middleware)),
            container=getattr(middleware, "container", None),
        )


class MiddlewareAdapterRegistry:
    """Registry for middleware adapters."""

    def __init__(self) -> None:
        """Initialise an empty registry.

        Use :meth:`with_defaults` for a pre-populated instance with
        built-in middleware adapters.
        """
        self._adapters: list[_MiddlewareAdapterProtocol] = []

    @classmethod
    def _default_entries(cls) -> dict[str, _MiddlewareAdapterProtocol]:
        """Declare the built-in middleware adapters, most specific first."""
        return {
            "starlette": _StarletteMiddlewareAdapter(),
            "di_scope": _DIScopeMiddlewareAdapter(),
            "http": _HTTPMiddlewareAdapterBase(),
            "tuple": _TupleMiddlewareAdapter(),
        }

    @classmethod
    def with_defaults(cls) -> MiddlewareAdapterRegistry:
        """Create a registry pre-populated with the built-in adapters.

        Default order matters: more specific adapters register first so
        custom adapters (inserted at the head) take precedence.
        """
        registry = cls()
        for adapter in cls._default_entries().values():
            registry.add_adapter(adapter)
        return registry

    def add_adapter(self, adapter: _MiddlewareAdapterProtocol) -> None:
        """Add a custom middleware adapter."""
        self._adapters.insert(
            0,
            adapter,
        )  # LIFO order so custom adapters take precedence

    def adapt(self, middleware: Any) -> StarletteMiddleware:
        """Adapt a middleware object using registered adapters."""
        for adapter in self._adapters:
            if adapter.can_adapt(middleware):
                return adapter.adapt(middleware)

        # Final fallback: Quadkit Middleware Adapter
        from quadkit.web.middleware.adapter import _QuadkitMiddlewareAdapter

        return StarletteMiddleware(_QuadkitMiddlewareAdapter, quadkit_mw=middleware)
