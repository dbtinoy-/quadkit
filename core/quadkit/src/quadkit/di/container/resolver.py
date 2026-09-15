"""DI container resolver — read-only resolution phase."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import (
    TYPE_CHECKING,
    Any,
    TypeVar,
    cast,
)

from quadkit.contracts.exceptions.provider import ModuleVisibilityError
from quadkit.di.context import _module_graph, check_visibility, get_current_module
from quadkit.di.module.errors import format_visibility_error
from quadkit.di.resolution.registry import ServiceRegistry
from quadkit.di.resolution.resolver import ServiceResolver
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from quadkit.di.container.scope import Scope
    from quadkit.di.extensions.strategies import ResolutionStrategy
    from quadkit.di.resolution.invoker import FunctionInvoker
    from quadkit.di.resolution.type_hints import BoundedCache

T = TypeVar("T")
logger = get_logger(__name__)


class ContainerResolverImpl:
    """Read-only service resolution.

    Implements ContainerResolverProtocol from quadkit-contracts.
    Used during Provider.boot() and at runtime after registration is complete.

    Args:
        registry: The shared service registry.
        service_resolver: The low-level service resolver.
        invoker: The function invoker for call().
        hints_cache: Bounded cache for type hints (used by invoker).
        scope_factory: Factory callable that produces a new Scope.
        parent_resolver: The parent container's resolver for hierarchical resolution.
    """

    def __init__(
        self,
        registry: ServiceRegistry,
        service_resolver: ServiceResolver,
        invoker: FunctionInvoker,
        hints_cache: BoundedCache,
        scope_factory: Callable[[], Scope],
        parent_resolver: ContainerResolverImpl | None = None,
    ) -> None:
        self._registry = registry
        self._service_resolver = service_resolver
        self._invoker = invoker
        self._hints_cache = hints_cache
        self._scope_factory = scope_factory
        self._parent_resolver = parent_resolver

    # -- Resolution ----------------------------------------------------------

    async def resolve(
        self, service_type: type[T], *, bypass_visibility: bool = False
    ) -> T:
        """Asynchronously resolve a service by its registered type.

        Args:
            service_type: The service type to resolve.
            bypass_visibility: If True, skip module visibility enforcement.

        Returns:
            The resolved service instance.

        Raises:
            ModuleVisibilityError: If module context lacks visibility over the service.
        """
        if not bypass_visibility:
            if not check_visibility(service_type):
                module = get_current_module()
                consumer_name = module.__name__ if module else "unknown"
                graph = _module_graph.get()

                if (
                    graph is not None
                    and module is not None
                    and hasattr(graph, "find_modules_exporting")
                ):
                    consumer_node = (
                        graph.get_module(module)
                        if hasattr(graph, "get_module")
                        else None
                    )
                    consumer_imports = [
                        imported.__name__
                        for imported in getattr(consumer_node, "imports", [])
                    ]
                    exporting_nodes = graph.find_modules_exporting(service_type)
                    exporting_names = [node.name for node in exporting_nodes]
                    exported_types = sorted(
                        {
                            export.__name__
                            for node in exporting_nodes
                            for export in getattr(node, "exports", [])
                        }
                    )
                    message = format_visibility_error(
                        consumer_module=consumer_name,
                        consumer_provider=consumer_name,
                        provider_module=exporting_names,
                        service_type=service_type.__name__,
                        exported_types=exported_types,
                        consumer_imports=consumer_imports,
                    )
                    hint = (
                        f"Import one of {exporting_names or ['the exporting module']} "
                        f"into {consumer_name}, or make it global."
                    )
                else:
                    message = (
                        f"Module '{consumer_name}' cannot resolve "
                        f"'{service_type.__name__}': not in its exports or global scope"
                    )
                    hint = "Import the module that exports this service, or make it global."

                raise ModuleVisibilityError(
                    message,
                    consumer_module=consumer_name,
                    service_type=service_type.__name__,
                    hint=hint,
                )
        return cast("T", await self._service_resolver.resolve(service_type))

    def resolve_sync(self, service_type: type[T]) -> T:
        """Synchronously resolve an already-instantiated singleton.

        Only works for singletons that have already been instantiated (e.g. during boot).

        Args:
            service_type: The service type to resolve.

        Returns:
            The resolved instance.

        Raises:
            UnresolvableDependencyError: If not a singleton or not instantiated.
        """
        from quadkit.contracts.exceptions import UnresolvableDependencyError

        descriptor = self._registry.get(service_type)
        if descriptor is not None and descriptor.is_instantiated:
            return cast("T", descriptor.instance)

        if self._parent_resolver:
            return self._parent_resolver.resolve_sync(service_type)

        raise UnresolvableDependencyError(
            f"Cannot resolve {service_type} synchronously: "
            "not an instantiated singleton."
        )

    async def resolve_optional(self, service_type: type[T]) -> T | None:
        """Resolve a service, returning None if not registered.

        Args:
            service_type: The type to resolve.

        Returns:
            The resolved instance or None if not registered.
        """
        if self.has(service_type):
            return await self.resolve(service_type)
        return None

    async def resolve_all(self, service_type: type[T]) -> list[T]:
        """Resolve all registered implementations that are subtypes of a service type.

        Args:
            service_type: The base type whose implementations to resolve.

        Returns:
            A list of resolved instances for matching registrations.
        """
        results: list[T] = []
        for registered_type in (d.service_type for d in self._registry.all()):
            if isinstance(registered_type, type) and issubclass(
                registered_type,
                service_type,
            ):
                results.append(await self.resolve(registered_type))
        if self._parent_resolver:
            results.extend(await self._parent_resolver.resolve_all(service_type))
        return results

    # -- Query ---------------------------------------------------------------

    def has(self, service_type: object) -> bool:
        """Check if a service is registered."""
        if self._registry.has(service_type):
            return True
        return (
            self._parent_resolver.has(service_type) if self._parent_resolver else False
        )

    def is_singleton(self, service_type: object) -> bool:
        """Check if a service is registered as a singleton."""
        return self._registry.is_singleton(service_type)

    def _registered_services(self) -> list[str]:
        """Get all registered service names."""
        services = {
            getattr(d.service_type, "__name__", str(d.service_type))
            for d in self._registry.all()
        }
        if self._parent_resolver:
            services.update(self._parent_resolver._registered_services())
        return sorted(services)

    # -- Call ----------------------------------------------------------------

    async def call(
        self,
        func: Callable[..., Awaitable[T] | T],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Call a function with dependency injection (Protocol implementation)."""
        return cast("T", await self._call(func, *args, **kwargs))

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

    # -- Scoping -------------------------------------------------------------

    def create_scope(self) -> Scope:
        """Create a request-scoped resolution context."""
        return self._scope_factory()

    @asynccontextmanager
    async def scope(self) -> AsyncIterator[Scope]:
        """Async context manager for a request-scoped container.

        Yields:
            A fresh Scope instance, disposed on exit.
        """
        s = self.create_scope()
        try:
            yield s
        finally:
            await s.dispose()

    # -- Internal (for Scope use) --------------------------------------------

    def _get_descriptor(self, service_type: type) -> Any:
        """Internal: Get descriptor for a service type. For Scope use only."""
        return self._registry.get(service_type)

    async def _create_with_injection(
        self,
        implementation: type,
        service_type: type,
    ) -> Any:
        """Internal: Create instance with DI. For Scope use only."""
        return await self._service_resolver.create_with_injection(
            implementation, service_type
        )


__all__ = ["ContainerResolverImpl"]
