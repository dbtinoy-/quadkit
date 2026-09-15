"""Introspection and validation surface for the DI container."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from quadkit.di.container.validation import OrphanedRegistration

if TYPE_CHECKING:
    from quadkit.di.container.container import Container
    from quadkit.di.container.validation import ContainerValidator
    from quadkit.di.resolution.diagnostics import ContainerDiagnostics
    from quadkit.di.resolution.registry import ServiceRegistry


class ContainerIntrospectionMixin:
    """Validation wrappers and diagnostic dumps delegating to collaborators."""

    if TYPE_CHECKING:
        _validator: ContainerValidator
        _diagnostics: ContainerDiagnostics
        _registry: ServiceRegistry
        _parent: Container | None

    def validate(self) -> list[str]:
        """Validate the container configuration.

        Checks:
        - All registered services have resolvable dependencies (missing dependencies)
        - No circular dependencies across the entire graph
        - No scope violations (singleton depending on scoped/transient)

        Returns:
            List of validation issues (empty if valid).
        """
        return self._validator.validate()

    def validate_no_orphans(self) -> list[OrphanedRegistration]:
        """Find registrations that no other service depends on.

        This is a development-time validator to identify dead code
        services that are registered but never used.

        Returns:
            List of potentially orphaned registrations.
        """
        return self._validator.validate_no_orphans()

    def _registered_services(self) -> list[str]:
        """Get all registered service names."""
        services = {
            getattr(d.service_type, "__name__", str(d.service_type))
            for d in self._registry.all()
        }
        if self._parent:
            services.update(self._parent._registered_services())
        return sorted(services)

    # -- Diagnostics -------------------------------------------------------

    def dump_registrations(self) -> list[dict[str, Any]]:
        """Return a JSON-serialisable snapshot of all container registrations."""
        return self._diagnostics.dump_registrations()

    def dump_dependency_graph(self) -> dict[str, list[str]]:
        """Return an adjacency map of service → direct dependency names."""
        return self._diagnostics.dump_dependency_graph()

    def log_registrations(self) -> None:
        """Log a human-readable table of all container registrations."""
        self._diagnostics.log_registrations()
