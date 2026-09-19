"""Result utility functions — as_result, as_result_sync, collect, partition, try_catch."""

from __future__ import annotations

from functools import wraps
from typing import (
    TYPE_CHECKING,
    Any,
    ParamSpec,
    TypeVar,
    cast,
)

from quadkit.result.types import Err, Ok, Result

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Iterable

E = TypeVar("E")
T = TypeVar("T")
U = TypeVar("U")
P = ParamSpec("P")


def as_result(
    *exceptions: type[Exception],
) -> Callable[
    [Callable[P, Awaitable[T]]], Callable[P, Awaitable[Result[T, Exception]]]
]:
    """Decorator to capture exceptions and return a ``Result`` — **async functions** (canonical).

    For sync functions use :func:`as_result_sync`.

    At least one exception type must be specified to prevent silently wrapping
    unexpected infrastructure failures.

    Args:
        *exceptions: Exception types to catch and wrap in ``Err``.

    Raises:
        TypeError: If called with no exception types.

    Example::

        @as_result(IOError, TimeoutError)
        async def fetch(url: str) -> bytes:
            return await client.get(url)
    """
    if not exceptions:
        raise TypeError(
            "as_result() requires at least one exception type. "
            "Example: @as_result(IOError) — "
            "use explicit types to avoid silently catching infrastructure errors."
        )
    catch = exceptions

    def decorator(
        func: Callable[P, Awaitable[T]],
    ) -> Callable[P, Awaitable[Result[T, Exception]]]:
        @wraps(func)
        async def async_wrapper(
            *args: Any,
            **kwargs: Any,
        ) -> Result[T, Exception]:
            try:
                return Ok(await func(*args, **kwargs))
            except catch as e:
                return Err(e)

        return async_wrapper

    return decorator


def as_result_sync(
    *exceptions: type[Exception],
) -> Callable[[Callable[P, T]], Callable[P, Result[T, Exception]]]:
    """Decorator to capture exceptions and return a ``Result`` — **sync functions only**.

    For async functions use :func:`as_result` (the canonical async variant).

    At least one exception type must be specified to prevent silently wrapping
    unexpected infrastructure failures.

    Args:
        *exceptions: Exception types to catch and wrap in ``Err``.

    Raises:
        TypeError: If called with no exception types.

    Example::

        @as_result_sync(ValueError, KeyError)
        def parse(data: str) -> int:
            return int(data)
    """
    if not exceptions:
        raise TypeError(
            "as_result_sync() requires at least one exception type. "
            "Example: @as_result_sync(ValueError) — "
            "use explicit types to avoid silently catching infrastructure errors."
        )
    catch = exceptions

    def decorator(func: Callable[P, T]) -> Callable[P, Result[T, Exception]]:
        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Result[T, Exception]:
            try:
                return Ok(func(*args, **kwargs))
            except catch as e:
                return Err(e)

        return sync_wrapper

    return decorator


def collect(results: Iterable[Result[T, E]]) -> Result[list[T], E]:
    """Collect an iterable of Results into a Result of a list."""
    values = []
    for r in results:
        if r.is_err():
            return cast("Result[list[T], E]", r)
        values.append(r.unwrap())
    return Ok(values)


def partition(results: Iterable[Result[T, E]]) -> tuple[list[T], list[E]]:
    """Partition results into successes and failures."""
    oks: list[T] = []
    errs: list[E] = []
    for r in results:
        if r.is_ok():
            oks.append(r.unwrap())
        else:
            errs.append(r.unwrap_err())
    return oks, errs


def try_catch(
    catch: tuple[type[Exception], ...],
    func: Callable[P, Awaitable[T]],
    *args: P.args,
    **kwargs: P.kwargs,
) -> Awaitable[Result[T, Exception]]:
    """Execute an async function and return its result as Ok, or Err if a listed exception occurs.

    This is the canonical (async-first) variant.  Callers must declare which
    exception types are expected failures; unexpected exceptions propagate normally.

    For sync functions use :func:`try_catch_sync`.

    Args:
        catch: A tuple of exception types to catch and wrap in ``Err``.
        func: The async callable to invoke.
        *args: Positional arguments forwarded to *func*.
        **kwargs: Keyword arguments forwarded to *func*.

    Example::

        result = await try_catch((IOError, TimeoutError), fetch, url)
    """
    return _try_catch_async_impl(catch, func, *args, **kwargs)


async def _try_catch_async_impl(
    catch: tuple[type[Exception], ...],
    func: Callable[P, Awaitable[T]],
    *args: P.args,
    **kwargs: P.kwargs,
) -> Result[T, Exception]:
    """Internal async implementation for try_catch."""
    try:
        return Ok(await func(*args, **kwargs))
    except catch as e:
        return Err(e)


def try_catch_sync(
    catch: tuple[type[Exception], ...],
    func: Callable[P, T],
    *args: P.args,
    **kwargs: P.kwargs,
) -> Result[T, Exception]:
    """Execute a sync function and return its result as Ok, or Err if a listed exception occurs.

    Unlike a bare ``try/except Exception``, callers must explicitly declare which
    exception types are expected failures.  Unexpected exceptions propagate normally.

    For async functions use :func:`try_catch` (the canonical async variant).

    Args:
        catch: A tuple of exception types to catch and wrap in ``Err``.
        func: The callable to invoke.
        *args: Positional arguments forwarded to *func*.
        **kwargs: Keyword arguments forwarded to *func*.

    Example::

        result = try_catch_sync((ValueError, KeyError), parse_int, "42")
    """
    try:
        return Ok(func(*args, **kwargs))
    except catch as e:
        return Err(e)


__all__ = [
    "as_result",
    "as_result_sync",
    "collect",
    "partition",
    "try_catch",
    "try_catch_sync",
]
