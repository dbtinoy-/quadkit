"""HTTP route metadata decorators.

These decorators attach route configuration to handler functions so that
any controller — regardless of which extension package it lives in — can
declare routes without importing from ``quadkit-web``.

The decorators themselves have zero dependencies: they only write a
``_route_config`` dict onto the decorated callable.

Example::

    from quadkit.contracts.web.routing import get, post

    class MyController(ControllerProtocol):
        @get("/items")
        async def list_items(self) -> list: ...

        @post("/items")
        async def create_item(self, body: Item) -> Item: ...
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


def _route(method: str, path: str, **kwargs: Any) -> Callable[..., Any]:
    """Create a route decorator for the given HTTP method.

    Args:
        method: HTTP method string (``"GET"``, ``"POST"``, etc.).
        path: URL path pattern for the route.
        **kwargs: Additional route configuration (e.g. ``summary``, ``tags``).

    Returns:
        A decorator that stamps ``_route_config`` onto the handler function.
    """

    def decorator(func: Any) -> Any:
        func._route_config = {"method": method, "path": path, **kwargs}
        return func

    return decorator


def get(path: str, **kwargs: Any) -> Callable[..., Any]:
    """Declare a GET route handler.

    Args:
        path: URL path pattern.
        **kwargs: Extra route configuration.

    Returns:
        Route decorator.
    """
    return _route("GET", path, **kwargs)


def post(path: str, **kwargs: Any) -> Callable[..., Any]:
    """Declare a POST route handler.

    Args:
        path: URL path pattern.
        **kwargs: Extra route configuration.

    Returns:
        Route decorator.
    """
    return _route("POST", path, **kwargs)


def put(path: str, **kwargs: Any) -> Callable[..., Any]:
    """Declare a PUT route handler.

    Args:
        path: URL path pattern.
        **kwargs: Extra route configuration.

    Returns:
        Route decorator.
    """
    return _route("PUT", path, **kwargs)


def delete(path: str, **kwargs: Any) -> Callable[..., Any]:
    """Declare a DELETE route handler.

    Args:
        path: URL path pattern.
        **kwargs: Extra route configuration.

    Returns:
        Route decorator.
    """
    return _route("DELETE", path, **kwargs)


def patch(path: str, **kwargs: Any) -> Callable[..., Any]:
    """Declare a PATCH route handler.

    Args:
        path: URL path pattern.
        **kwargs: Extra route configuration.

    Returns:
        Route decorator.
    """
    return _route("PATCH", path, **kwargs)


__all__ = ["delete", "get", "patch", "post", "put"]
