"""Service resolver for dependency injection container."""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
import inspect
from typing import TYPE_CHECKING, Any

from quadkit.contracts.exceptions import (
    CircularDependencyError,
    UnresolvableDependencyError,
)
from quadkit.di.extensions.interceptors import (
    InterceptorRegistry,
    wrap_with_interceptors,
)
from quadkit.di.resolution.descriptor import ServiceDescriptor, ServiceScope
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.di.protocols import InjectorProtocol
    from quadkit.di.resolution.registry import ServiceRegistry

logger = get_logger(__name__)


class ServiceResolver:
    """Resolves services from the registry with dependency injection."""

    #: Maximum nested resolution depth before a depth error is raised.
    #: ``0`` (default) disables the cap; set via :meth:`configure` from
    #: ``DiConfig.max_resolution_depth`` at provider boot.
    _max_resolution_depth: int = 0
    #: When True, each successful resolution is logged at debug level.
    #: Set via :meth:`configure` from ``DiConfig.debug_resolution``.
    _debug_resolution: bool = False

    @classmethod
    def configure(
        cls,
        *,
        max_resolution_depth: int = 0,
        debug_resolution: bool = False,
    ) -> None:
        """Apply process-wide resolution settings (called at DI provider boot).

        Args:
            max_resolution_depth: Cap on nested resolution depth
                (``0`` = unlimited).
            debug_resolution: Log every resolved service at debug level.
        """
        cls._max_resolution_depth = max_resolution_depth
        cls._debug_resolution = debug_resolution

    def __init__(
        self,
        registry: ServiceRegistry,
        injector: InjectorProtocol,
        parent: ServiceResolver | None = None,
        interceptor_registry: InterceptorRegistry | None = None,
    ) -> None:
        self._registry = registry
        self._injector = injector
        self._parent = parent
        self._interceptor_registry = interceptor_registry

        self._resolution_stack_var: ContextVar[list[object]] = ContextVar(
            "resolution_stack",
        )
        self._singleton_locks: dict[object, asyncio.Lock] = {}
        self._locks_guard = asyncio.Lock()

    # -- Public API --------------------------------------------------------

    async def resolve(self, service_type: object) -> Any:
        """Resolve a service by type."""
        instance = await self._do_resolve(service_type)
        if self._debug_resolution:
            logger.debug(
                "di.resolution.resolved",
                service=getattr(service_type, "__name__", repr(service_type)),
            )
        return instance

    def has(self, service_type: object) -> bool:
        """Check if registered."""
        if self._registry.has(service_type):
            return True
        return self._parent.has(service_type) if self._parent else False

    def can_resolve(self, service_type: object) -> bool:
        """Check if can be resolved."""
        if self.has(service_type):
            return True
        return bool(
            inspect.isclass(service_type)
            and getattr(service_type, "__quadkit_inject__", False)
        )

    async def create_with_injection(
        self,
        implementation: type,
        service_type: type,
    ) -> Any:
        """Create an instance with full DI. Used by Scope."""
        stack = self._get_stack()
        stack.append(service_type)
        try:
            return await self._injector.instantiate(implementation, force_inject=True)
        finally:
            stack.pop()

    # -- Resolution pipeline -----------------------------------------------

    async def _do_resolve(self, service_type: object) -> Any:
        """Core resolution pipeline.

        This is the internal implementation called by :meth:`resolve`.  The
        public :meth:`resolve` method documents the exceptions; this helper
        propagates them.  See also :meth:`_resolve_unregistered`.
        """
        self._check_circular(service_type)

        # Unwrap Annotated[T, Inject(...)]
        real_type, inject_name = self._unwrap_annotated(service_type)
        if real_type is not None:
            if inject_name:
                return await self._do_resolve(inject_name)
            return await self._do_resolve(real_type)

        descriptor = self._registry.get(service_type)

        if descriptor is None:
            if self._parent:
                return await self._parent.resolve(service_type)
            return await self._resolve_unregistered(service_type)

        if descriptor.scope is ServiceScope.SCOPED:
            name = getattr(service_type, "__name__", repr(service_type))
            from quadkit.contracts.exceptions.container import ScopedResolutionError

            raise ScopedResolutionError(
                f"Cannot resolve scoped service '{name}' outside of an "
                "active scope. Use async with container.scope() or "
                "container.create_scope().",
                service=name,
            )

        # Registry-style dispatch: a dict lookup never exhausts the enum,
        # so the defensive tail below stays statically reachable.
        handlers = {
            ServiceScope.SINGLETON: self._resolve_singleton,
            ServiceScope.TRANSIENT: self._create_instance,
        }
        handler = handlers.get(descriptor.scope)
        if handler is not None:
            return await handler(descriptor)

        # Defensive: ServiceScope has exactly three members today; this
        # guards against future enum additions slipping past dispatch.
        name = getattr(service_type, "__name__", repr(service_type))
        raise UnresolvableDependencyError(
            f"No handler for service scope {descriptor.scope!r} on '{name}'. "
            "This is a framework bug — please file an issue.",
            dependency=name,
        )

    async def _resolve_singleton(self, descriptor: ServiceDescriptor) -> Any:
        """Resolve singleton with double-checked locking."""
        if descriptor.is_instantiated:
            return descriptor.instance

        lock = await self._get_lock(descriptor.service_type)
        async with lock:
            # Re-check after acquiring lock
            current = self._registry.get(descriptor.service_type)
            if current and current.is_instantiated:
                return current.instance

            instance = await self._create_instance(descriptor)
            self._registry.update_singleton_instance(descriptor.service_type, instance)

            # Lock no longer needed — singleton exists (MAJ-7)
            async with self._locks_guard:
                self._singleton_locks.pop(descriptor.service_type, None)

            return instance

    async def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create a service instance from its descriptor."""
        impl = descriptor.implementation

        svc_type = descriptor.service_type
        # A named binding stores the service type as a (real_type, name) tuple.
        effective_type = svc_type[0] if isinstance(svc_type, tuple) else svc_type
        if not callable(impl):
            instance = impl
        elif inspect.isclass(impl):
            if not isinstance(effective_type, type):
                raise TypeError(
                    f"Expected a type for service_type, got {type(effective_type)}"
                )
            instance = await self.create_with_injection(impl, effective_type)
        else:
            try:
                result = impl(self)
            except TypeError:
                result = impl()
            if inspect.isawaitable(result):
                instance = await result
            else:
                instance = result

        if not isinstance(svc_type, type):
            return instance
        return wrap_with_interceptors(
            instance,
            svc_type,
            self._interceptor_registry,
        )

    async def _resolve_unregistered(self, service_type: object) -> Any:
        """Attempt to resolve a type not explicitly registered."""
        if not inspect.isclass(service_type):
            name = repr(service_type)
            raise UnresolvableDependencyError(
                f"Cannot resolve '{name}': not a class and not registered in the container. "
                "Register it via a Provider or a container lifetime call "
                "(singleton/transient/scoped/bind) before resolving.",
                dependency=name,
            )

        # Only auto-resolve classes explicitly marked for injection
        if getattr(service_type, "__quadkit_inject__", False):
            inst = await self.create_with_injection(service_type, service_type)
            return wrap_with_interceptors(
                inst, service_type, self._interceptor_registry
            )

        name = getattr(service_type, "__name__", repr(service_type))
        raise UnresolvableDependencyError(
            f"'{name}' is not registered in the container. "
            f"Register it via a Provider or a container lifetime call — "
            f"container.singleton({name}), container.transient({name}, factory), "
            "or container.scoped(...) — or mark it auto-wirable with @inject.",
            dependency=name,
        )

    # -- Circular dependency detection -------------------------------------

    def _get_stack(self) -> list[object]:
        stack = self._resolution_stack_var.get(None)
        if stack is None:
            stack = []
            self._resolution_stack_var.set(stack)
        return stack

    def _check_circular(self, service_type: object) -> None:
        stack = self._get_stack()
        if service_type in stack:
            cycle = [*stack, service_type]
            names = [getattr(cls, "__name__", repr(cls)) for cls in cycle]
            raise CircularDependencyError(" -> ".join(names))
        if self._max_resolution_depth and len(stack) >= self._max_resolution_depth:
            raise CircularDependencyError(
                f"Resolution depth exceeded {self._max_resolution_depth} "
                f"(current: {len(stack)}); possible circular or overly "
                "deep dependency graph"
            )

    # -- Annotated type unwrapping -----------------------------------------

    @staticmethod
    def _unwrap_annotated(
        service_type: object,
    ) -> tuple[object | None, object | None]:
        """Unwrap Annotated named metadata into a typed lookup key."""
        from typing import Annotated, get_args, get_origin

        if get_origin(service_type) is not Annotated:
            return None, None

        args = get_args(service_type)
        real_type = args[0]

        from quadkit.di.markers import Inject, Named

        for item in args[1:]:
            if isinstance(item, Inject) and item.name:
                return real_type, (real_type, item.name)
            if isinstance(item, Named):
                return real_type, (real_type, item.name)

        return real_type, None

    # -- Lock management ---------------------------------------------------

    async def _get_lock(self, service_type: object) -> asyncio.Lock:
        async with self._locks_guard:
            if service_type not in self._singleton_locks:
                self._singleton_locks[service_type] = asyncio.Lock()
            return self._singleton_locks[service_type]


__all__ = ["ServiceResolver"]
