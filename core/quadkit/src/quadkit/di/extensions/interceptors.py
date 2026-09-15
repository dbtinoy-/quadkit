"""DI-level interceptor utilities.

This module provides a simple interceptor protocol, a registry for
managing interceptors, and proxy logic that can wrap any object so that
method calls are dispatched through the interceptor chain.  The core
``Container`` is updated to consult the registry when resolving services
and will automatically proxy instances that have interceptors registered.

The design is deliberately lightweight and has no dependency on the
web-specific interceptor protocols; those live in
``quadkit-web/src/quadkit/web/protocols.py``.  This module is intended to
be usable by *any* extension package that wants to intercept service
calls.
"""

from __future__ import annotations

import inspect
from threading import Lock
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


class MethodInvocation:
    """Represents a single method call on an object.

    ``Interceptor`` implementations receive an instance of this class and
    may inspect or modify ``args``/``kwargs`` before calling ``proceed``.
    """

    def __init__(
        self,
        target: Any,
        method_name: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        method: Callable[..., Any],
    ) -> None:
        self.target = target
        self.method_name = method_name
        self.args = args
        self.kwargs = kwargs
        self.method = method

    def proceed(self) -> Any:
        """Synchronously invoke the underlying method.  The caller is
        responsible for awaiting the result if it is a coroutine.
        """
        return self.method(*self.args, **self.kwargs)


class DIInterceptor(Protocol):
    """Protocol for DI-level interceptors.

    ``intercept`` is invoked for every method call on a proxied service.
    Interceptors are free to execute code before and after ``next_handler``
    is called, to transform arguments/results, or to short-circuit the
    call entirely.
    """

    async def intercept(
        self,
        invocation: MethodInvocation,
        next_handler: Callable[[], Awaitable[Any]],
    ) -> Any: ...


class InterceptorChain:
    """Sequential executor for a list of interceptors.

    This is essentially the same logic as the web adapter's ``AOPInterceptorChain``
    but without any HTTP-specific semantics.
    """

    def __init__(self, interceptors: list[DIInterceptor]) -> None:
        self._interceptors = interceptors
        self._index = 0

    async def proceed(self, invocation: MethodInvocation) -> Any:
        if self._index >= len(self._interceptors):
            result = invocation.proceed()
            if inspect.isawaitable(result):
                return await result
            return result

        interceptor = self._interceptors[self._index]
        self._index += 1

        async def _next() -> Any:
            return await self.proceed(invocation)

        return await interceptor.intercept(invocation, _next)


class _PrioritizedInterceptor:
    """Internal wrapper pairing an interceptor with its declared priority."""

    __slots__ = ("interceptor", "priority")

    def __init__(self, interceptor: DIInterceptor, priority: int) -> None:
        self.interceptor = interceptor
        self.priority = priority


class InterceptorRegistry:
    """Thread-safe registry mapping service types to DI interceptors.

    Interceptors are stored in ascending priority order (lower int = higher
    priority, consistent with ProviderPriority semantics). Reads are lock-free
    via snapshot; writes are protected by a threading.Lock.

    A container creates one registry instance and exposes it via
    ``container.interceptor_registry``; application code or providers may
    register interceptors during startup.
    """

    def __init__(self) -> None:
        self._global: list[_PrioritizedInterceptor] = []
        self._by_type: dict[type, list[_PrioritizedInterceptor]] = {}
        self._lock = Lock()

    def add_global(self, interceptor: DIInterceptor, priority: int = 0) -> None:
        """Register a global interceptor applied to all service resolutions.

        Args:
            interceptor: The DI interceptor to register.
            priority: Lower values run first (default 0).
        """
        entry = _PrioritizedInterceptor(interceptor, priority)
        with self._lock:
            self._global.append(entry)
            self._global.sort(key=lambda e: e.priority)

    def add_for_type(
        self,
        service_type: type,
        interceptor: DIInterceptor,
        priority: int = 0,
    ) -> None:
        """Register an interceptor for a specific service type.

        Args:
            service_type: The service type this interceptor applies to.
            interceptor: The DI interceptor to register.
            priority: Lower values run first (default 0).
        """
        entry = _PrioritizedInterceptor(interceptor, priority)
        with self._lock:
            entries = self._by_type.setdefault(service_type, [])
            entries.append(entry)
            entries.sort(key=lambda e: e.priority)

    def get_interceptors(self, service_type: type) -> list[DIInterceptor]:
        """Return interceptors for a service type, in priority order.

        Lock-free read via snapshot — consistent with HookRegistry pattern.
        Global interceptors precede type-specific ones.

        Args:
            service_type: The service type to look up.

        Returns:
            Ordered list of DIInterceptor instances.
        """
        global_snapshot = list(self._global)
        type_snapshot = list(self._by_type.get(service_type, []))
        out: list[DIInterceptor] = []
        out.extend(e.interceptor for e in global_snapshot)
        out.extend(e.interceptor for e in type_snapshot)
        return out


class Proxy:
    """Lightweight proxy that applies interceptors to an object.

    Only methods are wrapped; attribute access passes through.
    """

    def __init__(
        self, target: Any, service_type: type, interceptors: list[DIInterceptor]
    ) -> None:
        self._target = target
        self._service_type = service_type
        self._interceptors = interceptors

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._target, name)
        if not callable(attr):
            return attr

        async def intercepted(*args: Any, **kwargs: Any) -> Any:
            invocation = MethodInvocation(
                target=self._target,
                method_name=name,
                args=args,
                kwargs=kwargs,
                method=attr,
            )
            chain = InterceptorChain(self._interceptors)
            return await chain.proceed(invocation)

        return intercepted


def wrap_with_interceptors(
    instance: Any,
    service_type: type,
    registry: InterceptorRegistry | None,
) -> Any:
    """Return a proxied instance if interceptors are registered.

    If no registry is supplied or no interceptors exist for the given
    service type, the original instance is returned unchanged.  This helper
    is used by the DI container after creating a service object.
    """
    if registry is None:
        return instance
    interceptors = registry.get_interceptors(service_type)
    if not interceptors:
        return instance
    return Proxy(instance, service_type, interceptors)
