"""Runtime operations mixin: scoping, injected calls, and disposal."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import inspect
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from quadkit.contracts.core.scopes import ServiceScope
from quadkit.di.container.scope import Scope
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable
    import types

    from quadkit.di.container.container import Container
    from quadkit.di.container.registrar import ContainerRegistrarImpl
    from quadkit.di.extensions.strategies import ResolutionStrategy
    from quadkit.di.resolution.registry import ServiceRegistry

T = TypeVar("T")

logger = get_logger(__name__)


class ContainerRuntimeMixin:
    """Scope management, DI function invocation, and container disposal."""

    if TYPE_CHECKING:
        # Collaborators provided by Container on composition.
        from quadkit.di.container.registrar import ContainerRegistrarImpl
        from quadkit.di.resolution.invoker import FunctionInvoker
        from quadkit.di.resolution.registry import ServiceRegistry

        _registry: ServiceRegistry
        _invoker: FunctionInvoker
        _hints_cache: dict[Any, Any]
        _registrar: ContainerRegistrarImpl

    def create_scope(self) -> Scope:
        """Create a request-scoped resolution context."""
        return Scope(cast("Container", self))

    @asynccontextmanager
    async def scope(self) -> AsyncIterator[Scope]:
        """Async context manager for a request-scoped container.

        Creates a new :class:`~quadkit.di.container.scope.Scope` and
        disposes it automatically when the context exits.

        Usage::

            async with container.scope() as scoped:
                service = await scoped.resolve(UserService)

        Yields:
            A fresh :class:`~quadkit.di.container.scope.Scope` instance.
        """
        s = self.create_scope()
        try:
            yield s
        finally:
            await s.dispose()

    # -- Function calling with DI (Framework internal use only) ------------

    async def _call(
        self,
        func: Callable[..., Awaitable[T] | T],
        *args: Any,
        strategies: list[ResolutionStrategy] | None = None,
        **kwargs: Any,
    ) -> T:
        """Call a function with automatic dependency injection."""
        return cast(
            "T",
            await self._invoker.call(
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

    async def dispose(self) -> None:
        """Dispose the container and all internal singletons.

        Iterates through all registered singletons and disposes of those
        that implement AsyncDisposableProtocol or have a close/aclose method.
        """
        logger.debug("container.dispose_started")
        errors: list[Exception] = []

        for descriptor in reversed(list(self._registry.all())):
            if (
                descriptor.scope == ServiceScope.SINGLETON
                and descriptor.instance is not None
            ):
                instance = descriptor.instance
                # The container registers itself as a singleton (ContainerResolverProtocol).
                # Calling dispose() on self would recurse infinitely — skip it.
                if instance is self:
                    continue
                try:
                    if hasattr(instance, "dispose"):
                        result = instance.dispose()
                        if inspect.isawaitable(result):
                            await result
                    elif hasattr(instance, "close"):
                        result = instance.close()
                        if inspect.isawaitable(result):
                            await result
                    elif hasattr(instance, "aclose"):
                        await instance.aclose()
                except asyncio.CancelledError:
                    raise
                except (
                    RuntimeError,
                    OSError,
                    AttributeError,
                    ValueError,
                    TypeError,
                ) as err:
                    logger.warning(
                        "container.dispose_error",
                        type=type(instance).__name__,
                        error=str(err),
                    )
                    errors.append(err)

        self._registry.clear()
        self._hints_cache.clear()

        if errors:
            raise ExceptionGroup("Container dispose errors", errors)

    def bind(self, service_type: type[T], instance: T) -> None:
        """Bind a pre-built singleton instance, overwriting any existing binding.

        Unlike ``singleton()``, this works on frozen containers, making it
        suitable for updating singleton instances during the boot phase
        (e.g. wrapping a store with a tenancy decorator).

        The service *must* already be registered as a singleton.

        Args:
            service_type: The registered service type to rebind.
            instance: The replacement singleton instance.
        """
        self._registrar.bind(service_type, instance)

    def override(self, service_type: type[T], instance: T) -> None:
        """Replace a service registration for testing purposes.

        This method is restricted to containers created with ``testing_mode=True``.
        It works even on frozen containers, intended for test scenarios where
        you need to swap a real service with a fake or mock.

        Args:
            service_type: The service type to override.
            instance: The replacement instance.

        Raises:
            ContainerError: If the container is not in testing mode.
            ContainerError: If the service is not registered.
        """
        self._registrar.override(service_type, instance)

    # -- Lifecycle control -------------------------------------------------

    async def __aenter__(self) -> Self:
        """Enter async context manager - returns self."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        """Exit async context manager - disposes the container."""
        await self.dispose()
        logger.debug("container.dispose_completed")
