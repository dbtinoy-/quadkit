"""Request-scoped in-process cache backed by :mod:`contextvars`.

Each ASGI request runs in its own :class:`contextvars.Context`, so the
:class:`contextvars.ContextVar` used here provides automatic per-request
isolation with no additional locking.  Nothing is written to Redis or any
external store — the cache lives only in memory for the lifetime of a single
request.

Typical usage
-------------
::

    from quadkit.cache import cache_in_request

    @cache_in_request
    async def get_user_permissions(user_id: str) -> list[str]:
        return await db.fetch_permissions(user_id)

    # Within one request the underlying coroutine executes once regardless
    # of how many times get_user_permissions is called with the same args.
    # A separate request sees a completely independent cache dict.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
import contextvars
import functools
from typing import Any, TypeVar

_F = TypeVar("_F", bound=Callable[..., Coroutine[Any, Any, Any]])

# Each request context gets its own cache dict.  The default is deliberately
# left as `None` so that `get_request_cache()` can distinguish "cache not yet
# initialised for this request" from "cache initialised but empty".
_request_cache_var: contextvars.ContextVar[dict[str, Any] | None] = (
    contextvars.ContextVar("quadkit_request_cache", default=None)
)


def get_request_cache() -> dict[str, Any]:
    """Return the current request's cache dict, creating it if needed.

    The first call within a new request context allocates a fresh ``dict``
    and stores it via :meth:`ContextVar.set` so that all subsequent calls in
    the same context share it.

    Returns:
        The mutable cache dict for this request context.
    """
    cache = _request_cache_var.get(None)
    if cache is None:
        cache = {}
        _request_cache_var.set(cache)
    return cache


def clear_request_cache() -> None:
    """Reset the current request's cache to an empty state.

    Call this at the end of a request (e.g. in ASGI middleware teardown) if
    you need an explicit eviction guarantee rather than relying on the context
    being discarded by the ASGI server.
    """
    _request_cache_var.set({})


def cache_in_request(func: _F) -> _F:
    """Cache the result of an async function for the duration of the current request.

    The cache key is derived from the function's qualified name and all
    positional and keyword arguments.  Arguments must support a stable
    ``repr()`` so that logically equal calls produce the same key.

    - **Same request, same args** → cached value returned; wrapped coroutine
      is not awaited again.
    - **Same request, different args** → each distinct arg combination gets
      its own cache entry.
    - **Different requests** → each request has an isolated
      :class:`contextvars.ContextVar` context; they never share entries.

    Args:
        func: The async callable to wrap.  Must be a coroutine function.

    Returns:
        A coroutine function with identical signature that transparently
        caches results within the current request context.

    Example::

        @cache_in_request
        async def get_user_permissions(user_id: str) -> list[str]:
            return await db.fetch_permissions(user_id)
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        cache = get_request_cache()
        key = f"{func.__qualname__}:{args!r}:{sorted(kwargs.items())!r}"
        if key not in cache:
            cache[key] = await func(*args, **kwargs)
        return cache[key]

    return wrapper  # type: ignore[return-value]


__all__ = [
    "cache_in_request",
    "clear_request_cache",
    "get_request_cache",
]
