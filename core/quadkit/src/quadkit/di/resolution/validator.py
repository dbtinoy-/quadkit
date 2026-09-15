"""Graph validator — dependency-graph management and cycle detection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.di.resolution.store import ServiceStore
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.di.protocols import TypeHintResolverProtocol
    from quadkit.di.resolution.descriptor import ServiceDescriptor

logger = get_logger(__name__)


class GraphValidator:
    """Validates the DI dependency graph.

    Maintains an incremental dependency graph alongside the ``ServiceStore``
    and exposes two validation entry points:

    - :meth:`update_for_descriptor` — called on every registration to keep
      the graph up to date and immediately catch cycles at registration time.
    - :meth:`validate_graph` — full-graph sweep for missing dependencies and
      cycles, typically called before the container is frozen.
    """

    def __init__(
        self,
        store: ServiceStore,
        type_hint_resolver: TypeHintResolverProtocol | None,
    ) -> None:
        """Initialise the validator.

        Args:
            store: The service store whose descriptors are validated.
            type_hint_resolver: Resolver used to inspect constructor type
                hints and infer declared dependencies.  When ``None``, graph
                tracking is disabled and no cycle detection is performed.
        """
        self._store = store
        self._type_hint_resolver = type_hint_resolver
        self._dependency_graph: dict[object, list[object]] = {}

    # -- Public API --------------------------------------------------------

    def update_for_descriptor(self, descriptor: ServiceDescriptor) -> None:
        """Update the dependency graph for a newly added descriptor.

        Resolves the constructor type hints of *descriptor*'s implementation
        and records the inferred dependencies.  Has no effect when no
        ``type_hint_resolver`` was provided at construction time.

        Args:
            descriptor: The descriptor that was just added to the store.
        """
        if not self._type_hint_resolver:
            return
        if not hasattr(descriptor.implementation, "__mro__"):
            return

        try:
            deps = self._type_hint_resolver.get_type_dependencies(
                descriptor.implementation,
            )
            if deps:
                self._dependency_graph[descriptor.service_type] = list(deps)
            else:
                self._dependency_graph.pop(descriptor.service_type, None)
        except (TypeError, AttributeError):
            # Class without inspectable __init__ — skip silently.
            pass

    def validate_graph(self) -> list[str]:
        """Validate the entire dependency graph.

        Performs a depth-first traversal over all registered services,
        checking for:

        - **Circular dependencies** — any cycle in the resolution graph.
        - **Missing dependencies** — a service that depends on a type not
          registered in the container.

        Returns:
            A list of human-readable error messages.  An empty list means
            the graph is valid.
        """
        errors: list[str] = []
        descriptors = {d.service_type: d for d in self._store.all()}
        visited: set[object] = set()
        path: list[object] = []

        def _check_node(node_type: object) -> None:
            if node_type in path:
                cycle = [*path[path.index(node_type) :], node_type]
                cycle_names = [getattr(c, "__name__", str(c)) for c in cycle]
                errors.append(
                    f"Circular dependency detected: {' -> '.join(cycle_names)}"
                )
                return

            try:
                if node_type in visited:
                    return
                visited.add(node_type)
            except TypeError:
                pass

            path.append(node_type)

            deps = self._dependency_graph.get(node_type, [])
            for dep in deps:
                if dep not in descriptors:
                    if isinstance(dep, type) and dep.__module__ != "builtins":
                        errors.append(
                            f"Missing dependency: '{getattr(node_type, '__name__', str(node_type))}' "
                            f"depends on unregistered '{getattr(dep, '__name__', str(dep))}'",
                        )
                _check_node(dep)

            path.pop()

        for service_type in list(descriptors):
            if service_type not in visited:
                _check_node(service_type)

        return errors

    def clear(self) -> None:
        """Clear the stored dependency graph."""
        self._dependency_graph.clear()

    # -- Internal ----------------------------------------------------------

    def _check_eager_cycle(self, service_key: object) -> None:
        """Raise ``CircularDependencyError`` if *service_key* creates a cycle.

        Called immediately after a descriptor is registered so that cycles
        are surfaced at registration time rather than at first resolution.

        Args:
            service_key: The service type key of the newly registered
                descriptor.

        Raises:
            CircularDependencyError: When a cycle is detected.
        """
        if service_key not in self._dependency_graph:
            return

        visited: set[object] = set()
        path: list[object] = []

        def _dfs(current: object) -> None:
            if current in path:
                from quadkit.contracts.exceptions import CircularDependencyError

                cycle_start = path.index(current)
                chain = path[cycle_start:]
                names = [getattr(c, "__name__", repr(c)) for c in chain]
                names.append(getattr(current, "__name__", repr(current)))
                raise CircularDependencyError(" -> ".join(names))

            if current in visited:
                return

            visited.add(current)
            path.append(current)

            for dep in self._dependency_graph.get(current, []):
                _dfs(dep)

            path.pop()

        _dfs(service_key)

    def _build_dependency_graph(self) -> dict[object, list[object]]:
        """Return the current dependency graph.

        Rebuilds the graph from scratch by re-inspecting every descriptor
        currently held in the store.  Replaces the cached
        ``_dependency_graph`` in place and returns the new graph.

        Returns:
            A mapping from service type → list of its declared dependency
            types, as inferred from constructor type hints.
        """
        self._dependency_graph = {}
        for descriptor in self._store.all():
            self.update_for_descriptor(descriptor)
        return self._dependency_graph


__all__ = ["GraphValidator"]
