"""Observability decorators for automatic tracing and metrics.

Provides zero-config decorators that attach tracing spans and timing
metrics to async or sync functions.

Example::

    from quadkit.observability.decorators import traced, metered

    @traced("order_service")
    @metered("order_create_duration")
    async def create_order(data: dict) -> Order:
        ...
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import functools
import time
from typing import Any, TypeVar

from quadkit.monitor.services.core import ObservabilityService

F = TypeVar("F", bound=Callable[..., Any])


def _resolve_service(
    service: ObservabilityService | None = None,
) -> ObservabilityService:
    """Resolve ObservabilityService from provided instance or return a NoOp fallback.

    Order of resolution:
    1. Explicit service instance.
    2. New local NoOp instance as last resort.
    """
    return service if service is not None else ObservabilityService()


def traced(
    span_name: str | None = None,
    *,
    service: ObservabilityService | None = None,
) -> Callable[[F], F]:
    """Decorator that wraps a function in a tracing span.

    Automatically captures function name, arguments, and any raised
    exceptions as span events.

    Args:
        span_name: Explicit span name. Defaults to the qualified function name.
        facade: Specific facade instance. Uses module default if ``None``.

    Returns:
        Decorated function.
    """

    def decorator(fn: F) -> F:
        name = span_name or f"{fn.__module__}.{fn.__qualname__}"

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                obs = _resolve_service(service)
                with obs.trace(name) as span:
                    try:
                        result = await fn(*args, **kwargs)
                    except Exception as exc:  # instrumentation must not interfere with decorated fn exceptions
                        span.set_attribute("error", True)
                        span.add_event(
                            "exception",
                            {"type": type(exc).__name__, "message": str(exc)},
                        )
                        raise
                    return result

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            obs = _resolve_service(service)
            with obs.trace(name) as span:
                try:
                    result = fn(*args, **kwargs)
                except Exception as exc:  # instrumentation must not interfere with decorated fn exceptions
                    span.set_attribute("error", True)
                    span.add_event(
                        "exception",
                        {"type": type(exc).__name__, "message": str(exc)},
                    )
                    raise
                return result

        return sync_wrapper  # type: ignore[return-value]

    return decorator


def metered(
    metric_name: str | None = None,
    *,
    service: ObservabilityService | None = None,
) -> Callable[[F], F]:
    """Decorator that records function execution time as a histogram metric.

    Args:
        metric_name: Explicit metric name. Defaults to ``{module}.{qualname}.duration``.
        facade: Specific facade instance. Uses module default if ``None``.

    Returns:
        Decorated function.
    """

    def decorator(fn: F) -> F:
        name = metric_name or f"{fn.__module__}.{fn.__qualname__}.duration"

        if asyncio.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                obs = _resolve_service(service)
                start = time.perf_counter()
                try:
                    return await fn(*args, **kwargs)
                finally:
                    elapsed = time.perf_counter() - start
                    obs.histogram(name).record(elapsed)

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            obs = _resolve_service(service)
            start = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                obs.histogram(name).record(elapsed)

        return sync_wrapper  # type: ignore[return-value]

    return decorator


class TracedClass:
    """Class decorator that wraps every public method in a tracing span.

    Iterates over the class's own callables (skipping dunder and, by
    default, private methods) and replaces each one with a ``traced()``-
    wrapped version backed by *ObservabilityService*.

    Args:
        prefix: Span-name prefix. Defaults to the decorated class name.
        trace_private: Whether to also wrap single-underscore methods.
            Defaults to ``False``.

    Example::

        @traced_class("order_service")
        class OrderService:
            async def create(self, data: dict) -> Order: ...
            async def cancel(self, order_id: str) -> None: ...
    """

    def __init__(
        self,
        prefix: str | None = None,
        *,
        trace_private: bool = False,
    ) -> None:
        self.prefix = prefix
        self.trace_private = trace_private

    def __call__(self, cls: type) -> type:
        prefix = self.prefix or cls.__name__
        for name in list(vars(cls)):
            if name.startswith("__"):
                continue
            if not self.trace_private and name.startswith("_"):
                continue
            method = getattr(cls, name)
            if callable(method) and not isinstance(
                method, (staticmethod, classmethod, property)
            ):
                setattr(cls, name, traced(f"{prefix}.{name}")(method))
        return cls


def traced_class(
    prefix: str | None = None,
    *,
    trace_private: bool = False,
) -> TracedClass:
    """Factory that returns a :class:`TracedClass` decorator.

    Convenience wrapper so the decorator can be used with or without arguments::

        @traced_class
        class Foo: ...

        @traced_class("my_prefix")
        class Bar: ...

    Args:
        prefix: Span-name prefix. Defaults to the decorated class name.
        trace_private: Whether to also wrap single-underscore methods.

    Returns:
        A :class:`TracedClass` instance ready to decorate a class.
    """
    return TracedClass(prefix=prefix, trace_private=trace_private)


__all__ = [
    "TracedClass",
    "metered",
    "traced",
    "traced_class",
]
