"""Event type discovery utilities (M-26).

Automatically scans modules for Event subclasses so users don't have to
manually call ``DefaultMessageSerializer.register_event_type()`` for each one.

Example::

    from quadkit.events.handlers.discovery import discover_event_types, register_discovered_types
    from quadkit.events.adapters.base import DefaultMessageSerializer

    serializer = DefaultMessageSerializer()

    # Scan your domain module
    event_types = discover_event_types("myapp.domain.events")
    register_discovered_types(event_types, serializer)

Or wire it into EventsProvider via ``handler_modules`` config:

    config = EventsConfig(handler_modules=["myapp.domain.events"])
    # EventsProvider.boot() calls discover_and_register() automatically.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.events.adapters.base import DefaultMessageSerializer
    from quadkit.events.messages.event import Event
    from quadkit.events.schema.registry import SchemaRegistry

logger = get_logger(__name__)


def discover_event_types(
    module_path: str,
    recursive: bool = True,
) -> dict[str, type[Event]]:
    """Scan a module or package for all Event subclasses.

    Args:
        module_path: Dotted module path, e.g. ``"myapp.domain.events"``.
        recursive: If True, scan sub-packages recursively.

    Returns:
        Dict of event type name → event class.

    Example::

        types = discover_event_types("myapp.domain")
        # {"OrderCreated": <class OrderCreated>, "OrderShipped": <class ...>}
    """
    from quadkit.events.messages.event import Event as _Event

    discovered: dict[str, type[_Event]] = {}

    def _scan_module(mod_path: str) -> None:
        try:
            mod = importlib.import_module(mod_path)
        except ImportError as exc:
            logger.warning("discovery: cannot import %s — %s", mod_path, exc)
            return

        for _name, obj in inspect.getmembers(mod, inspect.isclass):
            if (
                issubclass(obj, _Event)
                and obj is not _Event
                and obj.__module__.startswith(mod_path.split(".", maxsplit=1)[0])
            ):
                discovered[obj.__name__] = obj

        if recursive and hasattr(mod, "__path__"):
            # It's a package — recurse into sub-modules
            for _importer, submod_name, _ispkg in pkgutil.walk_packages(
                mod.__path__,
                prefix=mod_path + ".",
            ):
                _scan_module(submod_name)

    _scan_module(module_path)

    if discovered:
        names = ", ".join(sorted(discovered))
        logger.debug("Discovered event types in %s: %s", module_path, names)
    else:
        logger.debug("No event types found in %s", module_path)

    return discovered


def register_discovered_types(
    event_types: dict[str, type[Event]],
    serializer: DefaultMessageSerializer | None = None,
    schema_registry: SchemaRegistry | None = None,
) -> int:
    """Register discovered event types with serializer and/or schema registry.

    Args:
        event_types: Dict from ``discover_event_types()``.
        serializer: Optional serializer to register types with.
        schema_registry: Optional schema registry to register types with.

    Returns:
        Number of types registered.
    """
    count = 0
    for name, cls in event_types.items():
        if serializer is not None:
            serializer.register_event_type(cls)
            count += 1
            logger.debug("Registered event type %s with serializer", name)

        if schema_registry is not None:
            try:
                schema_registry.register(cls)  # type: ignore[attr-defined]
                logger.debug("Registered event type %s with schema registry", name)
            except (ValueError, AttributeError) as exc:
                logger.warning(
                    "Could not register %s with schema registry: %s", name, exc
                )

    return count


def discover_and_register(
    module_paths: list[str],
    serializer: DefaultMessageSerializer | None = None,
    schema_registry: SchemaRegistry | None = None,
    recursive: bool = True,
) -> dict[str, type[Event]]:
    """Discover and register all event types from multiple module paths.

    Convenience function that combines ``discover_event_types`` and
    ``register_discovered_types``.

    Args:
        module_paths: List of module paths to scan.
        serializer: AsyncStringSerializerProtocol to register types with.
        schema_registry: Schema registry to register types with.
        recursive: Recurse into sub-packages.

    Returns:
        All discovered event types.
    """
    all_types: dict[str, type[Any]] = {}
    for path in module_paths:
        types = discover_event_types(path, recursive=recursive)
        all_types.update(types)

    if serializer or schema_registry:
        register_discovered_types(all_types, serializer, schema_registry)

    return all_types


__all__ = [
    "discover_and_register",
    "discover_event_types",
    "register_discovered_types",
]
