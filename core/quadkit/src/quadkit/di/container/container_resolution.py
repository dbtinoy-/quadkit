"""Resolution mixin: queries and service resolution.

Split out of :mod:`quadkit.di.container.container` — registrations and
resolution are separate concerns, and the resolution surface (visibility
enforcement, optional and bulk lookups, synchronous access) is the larger
half.
"""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    TypeVar,
    cast,
    get_args,
    get_origin,
    overload,
)

from quadkit.contracts.exceptions import UnresolvableDependencyError
from quadkit.contracts.exceptions.provider import ModuleVisibilityError
from quadkit.di.context import _module_graph, check_visibility, get_current_module
from quadkit.di.module.errors import format_visibility_error
from quadkit.di.resolution.invoker import FunctionInvoker

if TYPE_CHECKING:
    from quadkit.di.container.container import Container
    from quadkit.di.resolution.registry import ServiceRegistry
    from quadkit.di.resolution.resolver import ServiceResolver
    from quadkit.di.resolution.type_hints import BoundedCache

T = TypeVar("T")


class ContainerResolutionMixin:
    """Queries and resolution over the registered services."""

    if TYPE_CHECKING:
        # Collaborators provided by Container on composition.
        _parent: Container | None
        strict_mode: bool
        _registry: ServiceRegistry
        _hints_cache: BoundedCache
        _service_resolver: ServiceResolver

    # -- Query -------------------------------------------------------------

    def has(self, service_type: object) -> bool:
        """Check if a service is explicitly registered."""
        if self._registry.has(service_type):
            return True
        return self._parent.has(service_type) if self._parent else False

    @overload
    async def resolve_optional(self, service_type: type[T]) -> T | None: ...

    @overload
    async def resolve_optional(self, service_type: Any) -> Any | None: ...

    async def resolve_optional(self, service_type: Any) -> Any | None:
        """Resolve a service, returning None when this consumer can not use it.

        Provides graceful handling for optional dependencies without
        requiring callers to catch exceptions.  A caller asking optionally
        treats a service that is registered but not visible to its module the
        same way as one that was never registered: an optional integration is
        not a boot requirement.  ``strict_mode`` keeps the misconfiguration
        loud instead.

        Args:
            service_type: The type to resolve.

        Returns:
            The resolved instance or None if the service is not available to
            this consumer.

        Raises:
            ModuleVisibilityError: When the service is registered but not
                visible and ``strict_mode`` is enabled.
        """
        if self.has(service_type):
            try:
                return await self.resolve(service_type)
            except ModuleVisibilityError:
                if self.strict_mode:
                    raise
                return None
        if self.strict_mode:
            name = getattr(service_type, "__name__", repr(service_type))
            raise UnresolvableDependencyError(
                f"'{name}' is not registered in the container and "
                "strict_mode is enabled; register it or disable strict mode.",
                dependency=name,
            )
        return None

    @overload
    async def resolve_all(self, service_type: type[T]) -> list[T]: ...

    @overload
    async def resolve_all(self, service_type: Any) -> list[Any]: ...

    async def resolve_all(self, service_type: Any) -> list[Any]:
        """Resolve all registered implementations that are subtypes of a service type.

        Args:
            service_type: The base type whose implementations to resolve.

        Returns:
            A list of resolved instances for matching registrations.
        """
        results: list[Any] = []
        for registered_type in (d.service_type for d in self._registry.all()):
            if isinstance(registered_type, type) and issubclass(
                registered_type,
                service_type,
            ):
                results.append(await self.resolve(registered_type))
        if self._parent:
            results.extend(await self._parent.resolve_all(service_type))
        return results

    def is_singleton(self, service_type: object) -> bool:
        """Check if a service is registered as a singleton."""
        return self._registry.is_singleton(service_type)

    def create_invoker(self) -> FunctionInvoker:
        """Create a :class:`~quadkit.di.resolution.invoker.FunctionInvoker` bound to this container.

        Returns a new invoker that shares this container's service resolver and
        type-hint cache, so repeated calls to :meth:`FunctionInvoker.call` benefit
        from the warm cache without exposing the resolver's private attributes.

        Returns:
            A :class:`~quadkit.di.resolution.invoker.FunctionInvoker` configured
            with this container's resolver and hints cache.

        Example::

            invoker = container.create_invoker()
            result = await invoker.call(my_function)
        """
        return FunctionInvoker(self._service_resolver, self._hints_cache)  # type: ignore[arg-type]

    # -- Resolution --------------------------------------------------------

    @overload
    async def resolve(
        self, service_type: type[T], *, bypass_visibility: bool = False
    ) -> T: ...

    @overload
    async def resolve(
        self, service_type: Any, *, bypass_visibility: bool = False
    ) -> Any: ...

    async def resolve(
        self, service_type: Any, *, bypass_visibility: bool = False
    ) -> Any:
        """Asynchronously resolve a service by its registered type.

        Args:
            service_type: The service type to resolve.
            bypass_visibility: If True, skip module visibility enforcement.
                Use only in framework-internal resolution paths.

        Returns:
            The resolved service instance.

        Raises:
            ModuleVisibilityError: If the current module context does not
                have visibility over the requested service type.
        """
        if not bypass_visibility:
            if not check_visibility(service_type):
                module = get_current_module()
                consumer_name = module.__name__ if module else "unknown"
                graph = _module_graph.get()

                if get_origin(service_type) is Annotated:
                    annotated_args = get_args(service_type)
                    if annotated_args:
                        service_type = annotated_args[0]

                providing_module = self._registry.providing_module(service_type)
                if providing_module is module and module is not None:
                    # Private to the consuming module itself — no
                    # cross-module surface is involved.
                    return await self._service_resolver.resolve(service_type)

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

                    if not exporting_names:
                        if providing_module is None:
                            # Not registered through any module and not
                            # exported anywhere — a standalone or framework
                            # service, outside the module surface.
                            return await self._service_resolver.resolve(service_type)
                        providing_name = getattr(
                            providing_module, "__name__", "its provider module"
                        )
                        message = (
                            f"Module '{consumer_name}' cannot resolve "
                            f"'{service_type.__name__}': provided by "
                            f"'{providing_name}' but not exported by it"
                        )
                        hint = (
                            f"Export {service_type.__name__} from "
                            f"'{providing_name}', or provide it from a "
                            "global module."
                        )
                    else:
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
                            f"Import one of {exporting_names} "
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
        return await self._service_resolver.resolve(service_type)

    def resolve_sync(self, service_type: type[T]) -> T:
        """Synchronously resolve an already-instantiated singleton.

        This is intended for use in decorators or other synchronous contexts
        where async resolution is not possible. It ONLY works for singletons
        that have already been instantiated (e.g. during boot).

        Args:
            service_type: The service type to resolve.

        Returns:
            The resolved instance.

        Raises:
            UnresolvableDependencyError: If not a singleton or not instantiated.
        """
        descriptor = self._registry.get(service_type)
        if descriptor is not None and descriptor.is_instantiated:
            return cast("T", descriptor.instance)

        if self._parent:
            return self._parent.resolve_sync(service_type)

        from quadkit.contracts.exceptions import UnresolvableDependencyError

        raise UnresolvableDependencyError(
            f"Cannot resolve {service_type} synchronously: "
            "not an instantiated singleton."
        )
