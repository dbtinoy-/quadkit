"""Public type aliases and generics for the quadkit framework.

Canonical types used across core APIs.  Users should prefer these over
constructing types manually.

Callable signatures::

    from quadkit.types import ServiceFactory, MiddlewareFactory

    def boot_service(factory: ServiceFactory) -> Any: ...

Hook handler signatures::

    from quadkit.types import ActionHandler, FilterHandler
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

# ---------------------------------------------------------------------------
# Type Variables  (module-internal; not re-exported — define your own)
# ---------------------------------------------------------------------------

T = TypeVar("T")
E = TypeVar("E")
K = TypeVar("K")
V = TypeVar("V")

# ---------------------------------------------------------------------------
# Callable Signatures
# ---------------------------------------------------------------------------

ServiceFactory = Callable[[], Any]
"""Factory that creates a service instance synchronously.

Example::

    def my_service_factory() -> MyService:
        return MyService()
"""

AsyncServiceFactory = Callable[[], Awaitable[Any]]
"""Factory that creates a service instance asynchronously.

Example::

    async def my_async_service_factory() -> MyService:
        return await MyService.create()
"""

MiddlewareFactory = Callable[[Any], Awaitable[Any]]
"""Factory that produces a middleware handler.

Accepts a request or context object and returns a result or raises.
"""

GuardFunction = Callable[[Any], Awaitable[bool]]
"""Authorisation guard that checks whether an action is permitted.

Returns ``True`` if authorised, ``False`` otherwise.  Raises for
infrastructure errors.
"""

ResultHandler = Callable[[Any], "Awaitable[Any] | Any"]
"""Handler for successful results in a pipeline."""

ErrorHandler = Callable[[Any], "Awaitable[Any] | Any"]
"""Handler for errors in a pipeline."""

ActionHandler = Callable[..., Any]
"""Hook action handler — receives hook arguments, returns None."""

FilterHandler = Callable[..., Any]
"""Hook filter handler — receives a value, returns the (possibly modified) value."""

__all__ = [
    "ActionHandler",
    "AsyncServiceFactory",
    "ErrorHandler",
    "FilterHandler",
    "GuardFunction",
    "MiddlewareFactory",
    "ResultHandler",
    "ServiceFactory",
]
