"""Registry introspection utilities for Quadkit Framework.

Provides runtime discovery and metadata retrieval for all
:class:`~quadkit.primitives.registry.Registry` instances across the
framework.  Useful for debugging, admin dashboards, and extension
point catalogs.

Usage::

    from quadkit.primitives.registry import (
        RegistryIntrospector,
        registry_info,
    )
    from quadkit.logging import get_logger

    logger = get_logger(__name__)

    # Single registry
    info = registry_info(my_registry)

    # Discover all registries in the DI container
    catalog = await RegistryIntrospector.from_container(container)
    for entry in catalog.all_info():
        logger.info(
            "registry_found",
            registry_name=entry["name"],
            item_count=entry["count"],
        )
"""

from __future__ import annotations

import importlib.metadata
from typing import Any

from quadkit.logging import get_logger
from quadkit.primitives.registry.core import (
    BackendRegistry,
    Registry,
    StrategyRegistry,
)

logger = get_logger(__name__)


def registry_info(registry: Registry[Any, Any]) -> dict[str, Any]:
    """Return introspection metadata for a single registry.

    Args:
        registry: Any :class:`Registry` instance.

    Returns:
        Dict with ``name``, ``type``, ``count``, ``keys``,
        ``factory_count``, ``allow_overwrite``, and ``hooks``.
    """
    reg_type = "Registry"
    if isinstance(registry, BackendRegistry):
        reg_type = "BackendRegistry"
    elif isinstance(registry, StrategyRegistry):
        reg_type = "StrategyRegistry"

    hooks_count = len(registry._on_register_hooks) + len(
        registry._on_unregister_hooks,
    )

    return {
        "name": registry.name,
        "class": type(registry).__qualname__,
        "type": reg_type,
        "count": len(registry),
        "keys": list(registry.keys()),
        "factory_count": len(list(registry.factories())),
        "allow_overwrite": registry.allow_overwrite,
        "hooks": hooks_count,
    }


def entry_point_catalog() -> dict[str, list[dict[str, str]]]:
    """Discover all Quadkit entry-point groups and their entries.

    Scans ``importlib.metadata`` for every group whose name starts
    with ``quadkit.`` and returns a mapping of group name to a list
    of entry-point metadata dicts.

    Returns:
        ``{"the optional provider module": [{"name": "redis", "value": "..."}]}``
    """
    catalog: dict[str, list[dict[str, str]]] = {}

    try:
        from quadkit.contracts.core.constants import ALL_ENTRY_POINT_GROUPS
    except ImportError:
        ALL_ENTRY_POINT_GROUPS = {}

    for group in ALL_ENTRY_POINT_GROUPS:
        eps = importlib.metadata.entry_points(group=group)
        entries: list[dict[str, str]] = []
        for ep in eps:
            entries.append(
                {
                    "name": ep.name,
                    "value": str(ep.value),
                    "group": group,
                }
            )
        if entries:
            catalog[group] = entries

    return catalog


class RegistryIntrospector:
    """Aggregates introspection data across all registries.

    Collects :func:`registry_info` from every :class:`Registry`
    instance reachable through the DI container.
    """

    def __init__(self, registries: list[Registry[Any, Any]]) -> None:
        self._registries = registries

    @classmethod
    async def from_container(
        cls,
        container: Any,
    ) -> RegistryIntrospector:
        """Build an introspector by scanning the DI container.

        Resolves every binding whose type is a :class:`Registry` subclass.

        Args:
            container: A :class:`~quadkit.contracts.core.di.ContainerResolverProtocol`.

        Returns:
            A populated :class:`RegistryIntrospector`.
        """
        registries: list[Registry[Any, Any]] = []

        if hasattr(container, "resolve_all"):
            try:
                resolved = await container.resolve_all(Registry)
                registries.extend(resolved)
            except (LookupError, RuntimeError, TypeError):
                logger.debug("registry_introspection_resolve_all_failed")

        if not registries and hasattr(container, "_bindings"):
            for binding in getattr(container, "_bindings", {}).values():
                instance = getattr(binding, "instance", None)
                if isinstance(instance, Registry):
                    registries.append(instance)

        return cls(registries)

    def all_info(self) -> list[dict[str, Any]]:
        """Return metadata for every discovered registry.

        Returns:
            List of dicts from :func:`registry_info`.
        """
        return [registry_info(r) for r in self._registries]

    def summary(self) -> dict[str, Any]:
        """Return an aggregate summary of all registries.

        Returns:
            Dict with ``total_registries``, ``total_items``,
            ``entry_points``, and ``registries`` list.
        """
        infos = self.all_info()
        return {
            "total_registries": len(infos),
            "total_items": sum(i["count"] for i in infos),
            "entry_points": entry_point_catalog(),
            "registries": infos,
        }


__all__ = [
    "RegistryIntrospector",
    "entry_point_catalog",
    "registry_info",
]
