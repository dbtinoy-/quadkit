"""HTTP route decorators for defining endpoints.

Provides decorator functions for each HTTP method to register route handlers
with the Quadkit router. These decorators store route configuration on the
decorated function for later discovery by the routing system.

Example:
    >>> from quadkit.web.routing import get, post
    >>>
    >>> @get("/users")
    >>> async def list_users(request):
    ...     return {"users": []}
    >>>
    >>> @post("/users")
    >>> async def create_user(request):
    ...     data = await request.json()
    ...     return {"id": 1, "data": data}
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])


def route(method: str, path: str, **kwargs: Any) -> Callable[[F], F]:
    """Create a route decorator for the specified HTTP method.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.).
        path: URL path pattern for the route.
        **kwargs: Additional route configuration options.

    Returns:
        A decorator function that configures the route handler.
    """

    def decorator(func: F) -> F:
        # Use setattr to avoid ruff auto-converting to direct attribute access
        # which fails because RoutableProtocol is a Callable and ruff/mypy don't like
        # dynamic attributes on it without setattr.
        cast("Any", func)._route_config = {"method": method, "path": path, **kwargs}
        return func

    return decorator


def get(path: str, **kwargs: Any) -> Callable[[F], F]:
    """Register a GET route handler.

    Args:
        path: URL path pattern for the route.
        **kwargs: Additional route configuration.

    Returns:
        Configured route handler function.

    Example:
        >>> @get("/users")
        >>> async def list_users(request):
        ...     return {"users": []}
    """
    return route("GET", path, **kwargs)


def post(path: str, **kwargs: Any) -> Callable[[F], F]:
    """Register a POST route handler.

    Parameters annotated with a Pydantic ``BaseModel`` or ``DomainModel``
    subclass are automatically deserialised from the JSON request body by
    :class:`~quadkit.web.routing.parameter_binder.ParameterBinder` — no
    ``body()`` decorator is required.

    Args:
        path: URL path pattern for the route.
        **kwargs: Additional route configuration.

    Returns:
        Configured route handler function.

    Example:
        >>> @post("/users")
        >>> async def create_user(request):
        ...     data = await request.json()
        ...     return {"id": 1, "data": data}
    """
    return route("POST", path, **kwargs)


def put(path: str, **kwargs: Any) -> Callable[[F], F]:
    """Register a PUT route handler.

    Args:
        path: URL path pattern for the route.
        **kwargs: Additional route configuration.

    Returns:
        Configured route handler function.
    """
    return route("PUT", path, **kwargs)


def delete(path: str, **kwargs: Any) -> Callable[[F], F]:
    """Register a DELETE route handler.

    Args:
        path: URL path pattern for the route.
        **kwargs: Additional route configuration.

    Returns:
        Configured route handler function.
    """
    return route("DELETE", path, **kwargs)


def patch(path: str, **kwargs: Any) -> Callable[[F], F]:
    """Register a PATCH route handler.

    Args:
        path: URL path pattern for the route.
        **kwargs: Additional route configuration.

    Returns:
        Configured route handler function.
    """
    return route("PATCH", path, **kwargs)


def head(path: str, **kwargs: Any) -> Callable[[F], F]:
    """Register a HEAD route handler.

    Args:
        path: URL path pattern for the route.
        **kwargs: Additional route configuration.

    Returns:
        Configured route handler function.
    """
    return route("HEAD", path, **kwargs)


def options(path: str, **kwargs: Any) -> Callable[[F], F]:
    """Register an OPTIONS route handler.

    Args:
        path: URL path pattern for the route.
        **kwargs: Additional route configuration.

    Returns:
        Configured route handler function.
    """
    return route("OPTIONS", path, **kwargs)


def trace(path: str, **kwargs: Any) -> Callable[[F], F]:
    """Register a TRACE route handler.

    Args:
        path: URL path pattern for the route.
        **kwargs: Additional route configuration.

    Returns:
        Configured route handler function.
    """
    return route("TRACE", path, **kwargs)


def websocket(path: str, **kwargs: Any) -> Callable[[F], F]:
    """Register a WebSocket route handler.

    Args:
        path: URL path pattern for the WebSocket endpoint.
        **kwargs: Additional route configuration.

    Returns:
        Configured WebSocket handler function.
    """
    return route("WEBSOCKET", path, **kwargs)


# NOTE: Parameter decorators were moved to `parameters.py` which provides a
# full implementation (metadata storage and support for annotations).
# Keep imports local to the routing package to preserve backward compatibility:
