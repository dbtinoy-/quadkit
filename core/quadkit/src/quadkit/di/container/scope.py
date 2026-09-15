"""Request-scoped resolution context for the DI container."""

from __future__ import annotations

import asyncio
import inspect
from typing import (
    TYPE_CHECKING,
    Any,
    Self,
    TypeVar,
    cast,
)

from quadkit.contracts.core.scopes import ServiceScope
from quadkit.contracts.exceptions import UnresolvableDependencyError
from quadkit.di.extensions.interceptors import wrap_with_interceptors
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    import types

    from quadkit.di.container.container import Container
    from quadkit.di.extensions.strategies import ResolutionStrategy
    from quadkit.di.resolution.descriptor import ServiceDescriptor

T = TypeVar("T")

logger = get_logger(__name__)


class Scope:
    """Request-scoped resolution context.

    Caches scoped service instances for the lifetime of the scope.
    Singletons and transients delegate to the root container.

    Supports nested scopes (K-02): parent scopes can be specified to create
    hierarchical scoping where child scopes can access parent scope services.

    Usage::

        async with container.create_scope() as scope:
            session = await scope.resolve(DbSession)
            # same instance within this scope

    Nested scope usage::

        async with container.create_scope() as parent_scope:
            # parent scope
            async with parent_scope.create_scope() as child_scope:
                # child scope can access parent services
                session = await child_scope.resolve(DbSession)
    """

    def __init__(self, root: Container, parent: Scope | None = None) -> None:
        self._root = root
        self._parent = parent  # K-02: Parent scope for nested scoping
        self._cache: dict[type, Any] = {}
        self._disposables: list[Any] = []
        # Concurrent-creation dedup: service_type -> in-flight future, so
        # parallel resolve() calls for the same scoped service await one
        # instance instead of racing the cache check-then-create.
        self._inflight: dict[type, asyncio.Future[Any]] = {}

    async def resolve(self, service_type: type[T]) -> T:
        """Resolve a service from this scope.

        K-02: Falls back to parent scope if not found in current scope.
        """
        descriptor = self._root._get_descriptor(service_type)

        if descriptor is None:
            # K-02: Try parent scope
            if self._parent is not None:
                return await self._parent.resolve(service_type)
            raise UnresolvableDependencyError(
                f"Service {getattr(service_type, '__name__', repr(service_type))} "
                "is not registered",
            )

        if descriptor.scope == ServiceScope.SINGLETON:
            return await self._root.resolve(service_type)

        if descriptor.scope == ServiceScope.TRANSIENT:
            return cast("T", await self._create_instance(descriptor))

        # Scoped — cache per scope
        if service_type in self._cache:
            return cast("T", self._cache[service_type])

        # Dedup concurrent creation: while one task awaits an async
        # factory, other concurrent resolve() calls must wait for the same
        # instance (the "same instance within this scope" guarantee).
        pending = self._inflight.get(service_type)
        if pending is not None:
            return cast("T", await pending)
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._inflight[service_type] = future

        try:
            instance = await self._create_instance(descriptor)
        except BaseException as err:
            del self._inflight[service_type]
            if not future.cancelled():
                future.set_exception(err)
                # Mark the stored exception as retrieved: concurrent waiters
                # still receive it, but the creating task re-raises it itself,
                # so an otherwise-unobserved future would otherwise be logged
                # as "Future exception was never retrieved" at GC time.
                future.exception()
            raise
        self._cache[service_type] = instance
        self._inflight.pop(service_type, None)
        if not future.cancelled():
            future.set_result(instance)

        if (
            hasattr(instance, "aclose")
            or hasattr(instance, "dispose")
            or hasattr(instance, "close")
        ):
            self._disposables.append(instance)

        return cast("T", instance)

    def create_scope(self) -> Scope:
        """K-02: Create a child scope nested within this scope.

        The child scope can access services from both the root container
        and the parent scope.
        """
        return Scope(self._root, parent=self)

    async def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create a service instance from its descriptor.

        After the raw object is constructed we consult the interceptor
        registry (if any) to see whether we need to return a proxy.
        """
        impl = descriptor.implementation

        if not callable(impl):
            instance = impl
        elif inspect.isclass(impl):
            instance = await self._root._create_with_injection(
                impl,
                cast("type", descriptor.service_type),
            )
        else:
            result = impl()
            if inspect.isawaitable(result):
                instance = await result
            else:
                instance = result

        # apply interceptors if registered
        return wrap_with_interceptors(
            instance,
            cast("type", descriptor.service_type),
            self._root.interceptor_registry,
        )

    async def _call(
        self,
        func: Callable[..., Awaitable[T] | T],
        *args: Any,
        strategies: list[ResolutionStrategy] | None = None,
        **kwargs: Any,
    ) -> T:
        """Call a function with dependency injection from this scope.

        .. warning::
            This method is for **framework-internal use only**. Applications
            should use constructor injection instead of calling this directly.
        """
        return cast(
            "T",
            await self._root._invoker.call(
                func,
                *args,
                strategies=strategies,
                **kwargs,
            ),
        )

    async def call(
        self,
        func: Callable[..., Awaitable[T] | T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Call a function with dependency injection (Protocol implementation)."""
        return await self._call(func, *args, **kwargs)

    def has(self, service_type: object) -> bool:
        """Check if a service is registered (delegates to root container)."""
        return self._root.has(service_type)

    async def resolve_optional(self, service_type: type[T]) -> T | None:
        """Resolve a service, returning None if not registered."""
        if self.has(service_type):
            return await self.resolve(service_type)
        return None

    async def resolve_all(self, service_type: type[T]) -> list[T]:
        """Resolve all registered implementations that are subtypes of a service type."""
        return await self._root.resolve_all(service_type)

    async def __aenter__(self) -> Self:
        """Enter async context manager - returns self."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Exit async context manager - disposes the scope."""
        await self.dispose()

    async def dispose(self) -> None:
        """Dispose all scoped resources."""
        errors: list[Exception] = []
        for disposable in reversed(self._disposables):
            try:
                if hasattr(disposable, "close"):
                    result = disposable.close()
                    if inspect.isawaitable(result):
                        await result
                elif hasattr(disposable, "aclose"):
                    await disposable.aclose()
                elif hasattr(disposable, "dispose"):
                    result = disposable.dispose()
                    if inspect.isawaitable(result):
                        await result
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 — every disposable must attempt dispose
                logger.warning(
                    "scope.dispose_error",
                    type=type(disposable).__name__,
                    error=str(err),
                )
                errors.append(err)
        self._cache.clear()
        self._disposables.clear()

        if errors:
            raise ExceptionGroup("Scope dispose errors", errors)


__all__ = ["Scope"]
