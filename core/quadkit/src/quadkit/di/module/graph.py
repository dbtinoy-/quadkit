"""Compiled module graph types.

These types represent the fully validated, ready-to-execute module graph
produced by the :class:`ModuleCompiler`.  They are consumed by the
:class:`ProviderOrchestrator` to drive registration, boot ordering,
and export validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.di.module.metadata import ModuleMetadata


@dataclass(frozen=True)
class ModuleNode:
    """A single module in the compiled graph.

    Represents one module after all imports, exports, and re-exports
    have been resolved.  The compiler produces one ``ModuleNode`` per
    unique module class in the graph.
    """

    module_class: type
    """The Python class decorated with ``@module``."""

    name: str
    """Resolved module name."""

    metadata: ModuleMetadata
    """The module's structural declarations (may be synthetic for DynamicModules)."""

    providers: list[type | Any]
    """Provider classes or pre-constructed instances from this module.

    For static modules, these are classes.  For dynamic modules, they
    may include already-instantiated provider objects.
    """

    imports: list[type]
    """Resolved module classes this module depends on (not DynamicModules —
    all resolved to their backing class)."""

    exports: frozenset[type]
    """Fully expanded export set.

    Re-exports (module classes in the original exports list) have been
    expanded to the concrete types exported by those modules.
    """

    is_global: bool
    """Whether this module's exports are universally visible."""

    is_dynamic: bool
    """Whether this node was created from a DynamicModule descriptor."""

    controllers: list[type] = field(default_factory=list)
    """Controller classes from this module."""

    health_providers: list[type | str] | None = None
    """Service types or paths to use for health checks (optional).

    - ``None`` (default): all providers in the module contribute.
    - ``[]`` (empty): no providers contribute; the module is always HEALTHY.
    - ``[SomeProvider, ...]``: only the listed provider classes/names contribute.
    """

    def __repr__(self) -> str:
        parts = [
            f"name={self.name!r}",
            f"providers={len(self.providers)}",
            f"exports={len(self.exports)}",
        ]
        if self.is_global:
            parts.append("global=True")
        if self.is_dynamic:
            parts.append("dynamic=True")
        return f"ModuleNode({', '.join(parts)})"


@dataclass(frozen=True)
class ProviderEntry:
    """A provider with its module context, ready for registration.

    Carries enough metadata for the orchestrator to:
    - Instantiate the provider (if it's a class)
    - Track module ownership
    - Log diagnostic information
    """

    provider: type | Any
    """Provider class (to be instantiated) or pre-built instance."""

    module_class: type | None
    """The module this provider belongs to.  ``None`` for standalone providers."""

    module_name: str | None
    """Human-readable module name.  ``None`` for standalone providers."""

    boot_level: int = 0
    """Parallel boot grouping.  Providers at the same level with no
    inter-dependencies can boot concurrently."""

    is_instance: bool = False
    """``True`` if :attr:`provider` is already an instantiated object
    (from a DynamicModule).  ``False`` if it's a class to be instantiated."""

    def __repr__(self) -> str:
        provider_name = (
            type(self.provider).__name__ if self.is_instance else self.provider.__name__
        )
        module_part = f" in {self.module_name}" if self.module_name else " (standalone)"
        return f"ProviderEntry({provider_name}{module_part}, level={self.boot_level})"


@dataclass(frozen=True)
class CompiledModuleGraph:
    """The fully validated, ready-to-execute module graph.

    Produced by :class:`ModuleCompiler` after successful compilation.
    Consumed by :class:`ProviderOrchestrator` to drive provider
    registration, boot ordering, and export validation.

    This object is immutable and safe to inspect for diagnostics.
    """

    nodes: dict[type, ModuleNode]
    """All modules in the graph, keyed by module class."""

    provider_order: list[ProviderEntry]
    """Providers in registration order.

    Imported module providers appear before importing module providers.
    Within a module, provider order follows the declaration order in
    ``providers=[]`` (or ``DynamicModule.providers``).
    """

    visibility: dict[type, frozenset[type]]
    """Visibility map: ``module_class → set of types visible to that module``.

    Each module can see:
    - Types provided by its own providers
    - Exports from imported modules
    - Exports from all global modules
    """

    global_exports: frozenset[type]
    """Union of all global module exports.

    These types are visible to every module without explicit import.
    """

    warnings: list[str] = field(default_factory=list)
    """Non-fatal issues detected during compilation.

    Examples: unused exports, shadowed imports, redundant global
    declarations.
    """

    # -- Query methods -----------------------------------------------------

    def get_module(self, cls: type) -> ModuleNode | None:
        """Look up a module node by its class."""
        return self.nodes.get(cls)

    def is_visible(self, from_module: type, service_type: type) -> bool:
        """Check if *service_type* is visible to *from_module*.

        Returns ``True`` if:
        - *service_type* is in the visibility set of *from_module*
        - *from_module* is not in the graph (standalone — no restrictions)
        """
        visible = self.visibility.get(from_module)
        if visible is None:
            return True  # Not a module — standalone, no restrictions
        return service_type in visible

    def get_providers_for_module(self, cls: type) -> list[ProviderEntry]:
        """Return all provider entries belonging to a specific module."""
        return [e for e in self.provider_order if e.module_class is cls]

    def get_module_names(self) -> list[str]:
        """Return all module names in the graph."""
        return [node.name for node in self.nodes.values()]

    def get_global_modules(self) -> list[ModuleNode]:
        """Return all global module nodes."""
        return [node for node in self.nodes.values() if node.is_global]

    def get_module_by_name(self, name: str) -> type | None:
        """Return the module class with the given ``__name__``, or None.

        Args:
            name: The module class name (e.g., ``'UserModule'``).

        Returns:
            The module class if found, None otherwise.
        """
        for module_cls in self.nodes:
            if module_cls.__name__ == name:
                return module_cls
        return None

    def get_exports_for_module(self, module_cls: type) -> frozenset[type]:
        """Return the set of service types exported by the given module.

        Args:
            module_cls: The module class to query.

        Returns:
            Frozenset of exported service types, or empty frozenset if not found.
        """
        node = self.nodes.get(module_cls)
        if node is None:
            return frozenset()
        return node.exports

    def get_importing_modules(self, module_cls: type) -> frozenset[type]:
        """Return all modules that import the given module.

        Args:
            module_cls: The module class to query.

        Returns:
            Frozenset of module classes that have ``module_cls`` in their imports.
        """
        return frozenset(
            cls for cls, node in self.nodes.items() if module_cls in node.imports
        )

    def find_modules_exporting(self, service_type: type) -> list[ModuleNode]:
        """Return modules that export the requested service type."""
        return [node for node in self.nodes.values() if service_type in node.exports]

    def get_dependency_chain(self, module_cls: type) -> list[type]:
        """Return the full transitive import chain for a module in BFS order.

        Args:
            module_cls: The root module class.

        Returns:
            List of module classes in BFS order starting with direct imports,
            then their imports, and so on. The root module itself is not included.
        """
        from collections import deque

        node = self.nodes.get(module_cls)
        if node is None:
            return []

        visited: set[type] = set()
        queue: deque[type] = deque()
        result: list[type] = []

        for dep in node.imports:
            if dep not in visited:
                visited.add(dep)
                queue.append(dep)

        while queue:
            current = queue.popleft()
            result.append(current)
            current_node = self.nodes.get(current)
            if current_node is not None:
                for dep in current_node.imports:
                    if dep not in visited:
                        visited.add(dep)
                        queue.append(dep)

        return result

    def get_boot_level(self, module_cls: type) -> int | None:
        """Return the boot level assigned to a module, or None if not found.

        Boot level 0 boots first (no dependencies); higher levels boot later.
        Derived from the ``boot_level`` of the module's provider entries.

        Args:
            module_cls: The module class to query.

        Returns:
            The boot level integer if the module has providers in the boot order,
            or None if the module is not in the graph or has no assigned boot level.
        """
        if module_cls not in self.nodes:
            return None
        for entry in self.provider_order:
            if entry.module_class is module_cls:
                return entry.boot_level
        return None

    def get_health_providers(self, module_cls: type) -> list[ProviderEntry]:
        """Get provider entries that contribute to this module's health checks.

        The list of contributing providers depends on the module's ``health_providers``
        configuration in its ``DynamicModule``:

        - ``None`` (default): all providers in the module contribute.
        - ``[]`` (empty): no providers contribute; the module is always HEALTHY.
        - ``[SomeProvider, ...]``: only the listed provider classes or names contribute.

        Args:
            module_cls: The module class to query.

        Returns:
            List of ProviderEntry for health-contributing providers.
            Empty list if module not found or health_providers=[].
        """
        node = self.nodes.get(module_cls)
        if node is None:
            return []

        all_providers = self.get_providers_for_module(module_cls)

        if node.health_providers is None:
            return all_providers

        if len(node.health_providers) == 0:
            return []

        specified = set(node.health_providers)
        filtered: list[ProviderEntry] = []
        for p in all_providers:
            provider = p.provider
            # Check by class identity (handles class-in-spec, class-in-entry)
            if provider in specified:
                filtered.append(p)
                continue
            # When provider is an instance, check its class against the spec
            if p.is_instance and type(provider) in specified:
                filtered.append(p)
                continue
            # Check by __name__ attribute (class name string match)
            if hasattr(provider, "__name__") and provider.__name__ in specified:
                filtered.append(p)
                continue
            # Check by name attribute (for Provider instances/classes with .name)
            if hasattr(provider, "name") and provider.name in specified:
                filtered.append(p)
        return filtered

    # -- Diagnostics -------------------------------------------------------

    def dump(self) -> dict[str, Any]:
        """Return a JSON-serialisable summary of the compiled graph.

        Useful for debugging and logging.
        """
        return {
            "modules": {
                node.name: {
                    "class": node.module_class.__name__,
                    "providers": len(node.providers),
                    "imports": [
                        self.nodes[imp].name
                        for imp in node.imports
                        if imp in self.nodes
                    ],
                    "exports": sorted(t.__name__ for t in node.exports),
                    "is_global": node.is_global,
                    "is_dynamic": node.is_dynamic,
                }
                for node in self.nodes.values()
            },
            "provider_order": [
                {
                    "provider": (
                        type(e.provider).__name__
                        if e.is_instance
                        else e.provider.__name__
                    ),
                    "module": e.module_name,
                    "boot_level": e.boot_level,
                }
                for e in self.provider_order
            ],
            "global_exports": sorted(t.__name__ for t in self.global_exports),
            "warnings": self.warnings,
        }

    def __repr__(self) -> str:
        return (
            f"CompiledModuleGraph("
            f"modules={len(self.nodes)}, "
            f"providers={len(self.provider_order)}, "
            f"global_exports={len(self.global_exports)}, "
            f"warnings={len(self.warnings)})"
        )
