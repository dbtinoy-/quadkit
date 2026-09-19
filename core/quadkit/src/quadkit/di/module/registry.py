"""ModuleRegistry — runtime ownership tracking.

Maps service types to their owning modules.  Populated during the
registration phase by the orchestrator, and queried during post-
registration export validation.

This is a runtime artifact — it exists only while the application is
running.  It is NOT part of the compiled graph (which is computed
before registration).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.di.module.errors import format_missing_export_error
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.di.module.graph import CompiledModuleGraph

logger = get_logger(__name__)


class ModuleRegistry:
    """Tracks which module owns which service registration.

    Populated by the orchestrator during ``register_all()``.  After
    registration completes and the container is frozen, the orchestrator
    calls :meth:`validate_exports` to verify that every declared export
    was actually registered.
    """

    def __init__(self) -> None:
        self._type_to_module: dict[type, type | None] = {}
        """service_type → module_class (None for standalone)."""

        self._module_to_types: dict[type | None, set[type]] = {}
        """module_class → set of service types registered by that module."""

        self._provider_to_module: dict[str, type | None] = {}
        """provider_name → module_class."""

    def register_ownership(
        self,
        service_type: type,
        module_class: type | None,
        provider_name: str | None = None,
    ) -> None:
        """Record that *service_type* was registered by a provider in *module_class*.

        Args:
            service_type: The type registered in the container.
            module_class: The module that owns the provider, or ``None``
                for standalone providers.
            provider_name: Name of the provider that registered this type.
        """
        self._type_to_module[service_type] = module_class

        if module_class not in self._module_to_types:
            self._module_to_types[module_class] = set()
        self._module_to_types[module_class].add(service_type)

        if provider_name:
            self._provider_to_module[provider_name] = module_class

    def register_provider(
        self,
        provider_name: str,
        module_class: type | None,
    ) -> None:
        """Record that a provider belongs to a module.

        Called before the provider's ``register()`` method runs.
        Actual type ownership is recorded via :meth:`register_ownership`
        during registration (or inferred post-hoc from the container).

        Args:
            provider_name: The provider's ``name`` attribute.
            module_class: The module that owns this provider.
        """
        self._provider_to_module[provider_name] = module_class

    def get_owner(self, service_type: type) -> type | None:
        """Get the module class that owns *service_type*, or ``None``.

        Returns ``None`` for standalone providers and for types not
        tracked by the registry.
        """
        return self._type_to_module.get(service_type)

    def get_module_services(self, module_class: type) -> frozenset[type]:
        """Get all service types registered by providers in *module_class*."""
        return frozenset(self._module_to_types.get(module_class, set()))

    def get_provider_module(self, provider_name: str) -> type | None:
        """Get the module that owns a provider by name."""
        return self._provider_to_module.get(provider_name)

    def validate_exports(
        self,
        graph: CompiledModuleGraph,
        container: Any | None = None,
    ) -> list[str]:
        """Validate that every declared export was actually registered.

        Called after all providers have registered and the container is
        frozen.  Checks each module's declared exports against the
        types actually registered by that module's providers.

        If *container* is provided, also checks ``container.has(export)``
        as a fallback for types registered by the provider but not
        tracked by the registry (e.g., when using factory registrations).

        Args:
            graph: The compiled module graph.
            container: Optional container for ``has()`` fallback check.

        Returns:
            List of error message strings.  Empty if all exports are
            satisfied.
        """
        errors: list[str] = []

        for module_class, node in graph.nodes.items():
            if not node.exports:
                continue

            registered = self._module_to_types.get(module_class, set())
            provider_names = self._get_provider_names_for_module(module_class)

            for export_type in node.exports:
                # Skip re-export references (module classes in exports
                # have already been expanded by the compiler)
                if export_type in graph.nodes:
                    continue

                # Check 1: Was it registered by this module's providers?
                if export_type in registered:
                    continue

                # Check 2: Is it in the container at all? (fallback)
                if container is not None and hasattr(container, "has"):
                    if container.has(export_type):
                        # Registered but not tracked — log warning
                        self._warnings_untracked(node.name, export_type)
                        continue

                errors.append(
                    format_missing_export_error(
                        module_name=node.name,
                        export_name=export_type.__name__,
                        provider_names=provider_names,
                        registered_types=[t.__name__ for t in registered],
                    ),
                )

        if errors:
            logger.warning(
                "module.export_validation_failed",
                error_count=len(errors),
            )
        else:
            logger.debug("module.export_validation_passed")

        return errors

    def _get_provider_names_for_module(self, module_class: type) -> list[str]:
        """Get names of providers belonging to a module."""
        return [
            name
            for name, mod in self._provider_to_module.items()
            if mod is module_class
        ]

    def _warnings_untracked(self, module_name: str, export_type: type) -> None:
        """Log a warning about an untracked export."""
        logger.debug(
            "module.export_untracked",
            module=module_name,
            export=export_type.__name__,
            message=(
                f"Export '{export_type.__name__}' in module '{module_name}' "
                f"is registered in the container but was not tracked by "
                f"the module registry.  This typically happens with factory "
                f"registrations."
            ),
        )

    # -- Diagnostics -------------------------------------------------------

    def dump(self) -> dict[str, Any]:
        """Return a JSON-serialisable summary of the registry."""
        module_summary: dict[str, list[str]] = {}
        for mod_cls, types in self._module_to_types.items():
            key = mod_cls.__name__ if mod_cls else "__standalone__"
            module_summary[key] = sorted(t.__name__ for t in types)
        return {
            "modules": module_summary,
            "total_types": len(self._type_to_module),
            "providers": dict(self._provider_to_module),
        }

    def __repr__(self) -> str:
        return (
            f"ModuleRegistry("
            f"types={len(self._type_to_module)}, "
            f"modules={len(self._module_to_types)}, "
            f"providers={len(self._provider_to_module)})"
        )
