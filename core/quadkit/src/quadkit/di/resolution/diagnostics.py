"""Diagnostics for dependency injection container."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.di.resolution.registry import ServiceRegistry
    from quadkit.di.resolution.type_hints import TypeHintResolverImpl

logger = get_logger(__name__)


class ContainerDiagnostics:
    """Provides diagnostic utilities for the DI container.

    Extracts introspection and logging logic to keep the main Container
    class focused on registration and resolution.
    """

    def __init__(
        self,
        registry: ServiceRegistry,
        type_hint_resolver: TypeHintResolverImpl,
    ) -> None:
        self._registry = registry
        self._type_hint_resolver = type_hint_resolver

    def dump_registrations(self) -> list[dict[str, Any]]:
        """Return a JSON-serialisable snapshot of all container registrations."""
        entries = []
        for descriptor in sorted(
            self._registry.all(),
            key=lambda d: getattr(d.service_type, "__name__", str(d.service_type)),
        ):
            svc_name = getattr(
                descriptor.service_type,
                "__name__",
                str(descriptor.service_type),
            )
            impl_name = (
                getattr(
                    descriptor.implementation,
                    "__name__",
                    str(descriptor.implementation),
                )
                if descriptor.implementation is not None
                else None
            )
            entries.append(
                {
                    "service": svc_name,
                    "implementation": impl_name,
                    "scope": descriptor.scope.value,
                    "has_instance": descriptor.instance is not None,
                },
            )
        return entries

    def dump_dependency_graph(self) -> dict[str, list[str]]:
        """Return an adjacency map of service → direct dependency names."""
        graph: dict[str, list[str]] = {}
        for descriptor in self._registry.all():
            svc_name = getattr(
                descriptor.service_type,
                "__name__",
                str(descriptor.service_type),
            )
            if descriptor.implementation is None or not inspect.isclass(
                descriptor.implementation,
            ):
                graph[svc_name] = []
                continue
            try:
                deps = self._type_hint_resolver.get_type_dependencies(
                    descriptor.implementation,
                )
                dep_names = [
                    getattr(d, "__name__", str(d))
                    for d in deps
                    if self._registry.has(d)
                ]
            except (TypeError, ValueError):
                dep_names = []
            graph[svc_name] = dep_names
        return graph

    def log_registrations(self) -> None:
        """Log a human-readable table of all container registrations."""
        entries = self.dump_registrations()
        if not entries:
            logger.debug("Container: no registrations")
            return
        logger.debug("Container registrations (%s services):", len(entries))
        for entry in entries:
            scope_tag = entry["scope"].upper().ljust(12)
            impl_part = (
                f" -> {entry['implementation']}" if entry["implementation"] else ""
            )
            instance_tag = " (instance=yes)" if entry["has_instance"] else ""
            logger.debug(
                "  [%s]  %s%s%s",
                scope_tag,
                entry["service"],
                impl_part,
                instance_tag,
            )


__all__ = ["ContainerDiagnostics"]
