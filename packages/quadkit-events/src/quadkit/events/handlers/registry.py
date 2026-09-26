"""Handler registry for automatic handler discovery and registration.

The registry enables auto-discovery of handlers from modules and
automatic registration with buses.
"""

# mypy: disable-error-code = annotation-unchecked

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import TYPE_CHECKING, Any

from quadkit.events.handlers.base import (
    CommandHandlerProtocol,
    EventHandlerProtocol,
    MultiEventHandlerProtocol,
    QueryHandlerProtocol,
)
from quadkit.primitives.registry import Registry

if TYPE_CHECKING:
    from collections.abc import Callable

    from quadkit.contracts.events import (
        CommandBusProtocol,
        EventBusProtocol,
        QueryBusProtocol,
    )


class HandlerRegistry:
    """Registry for handler discovery and registration.

    The registry provides:
    - Auto-discovery of handlers from modules
    - Registration with command, query, and event buses
    - Tracking of handler-message relationships

    Example:
        ```python
        # Create registry
        registry = HandlerRegistry()

        # Discover handlers from modules
        registry.discover("app.handlers")

        # Register with buses
        registry.register_with_buses(
            command_bus=command_bus,
            query_bus=query_bus,
            event_bus=event_bus
        )

        # Or use DI container for handler instantiation
        registry.register_with_container(container)
        ```
    """

    def __init__(self) -> None:
        """Initialize the handler registry."""

        # Internal Registry instances for unified introspection
        self._command_handlers: Registry[type, Any] = Registry(
            name="events.command_handlers",
            allow_overwrite=True,
        )
        self._query_handlers: Registry[type, Any] = Registry(
            name="events.query_handlers",
            allow_overwrite=True,
        )
        self._event_handlers: dict[type, list[Any]] = {}
        self._discovered_modules: set[str] = set()

    def load_decorators(self) -> None:
        """Load handlers from the global decorator registry (M-17).

        Call this explicitly to register handlers that were annotated with
        @command_handler, @event_handler, etc.
        """
        self._load_from_global_registry()

    def _load_from_global_registry(self) -> None:
        """Load handlers from the global decorator registry."""
        from quadkit.events.decorators.handlers import get_all_handlers

        for info in get_all_handlers("command"):
            if info.message_types:
                self.register_command_handler(info.message_types[0], info.handler)

        for info in get_all_handlers("query"):
            if info.message_types:
                self.register_query_handler(info.message_types[0], info.handler)

        for info in get_all_handlers("event"):
            for event_type in info.message_types:
                self.register_event_handler(event_type, info.handler)

    def register_command_handler(
        self,
        command_type: type,
        handler_type: Any,
    ) -> None:
        """Register a command handler.

        Args:
            command_type: The command class
            handler_type: The handler class
        """
        self._command_handlers.register(command_type, handler_type)

    def register_query_handler(
        self,
        query_type: type,
        handler_type: Any,
    ) -> None:
        """Register a query handler.

        Args:
            query_type: The query class
            handler_type: The handler class
        """
        self._query_handlers.register(query_type, handler_type)

    def register_event_handler(
        self,
        event_type: type,
        handler_type: Any,
    ) -> None:
        """Register an event handler.

        Args:
            event_type: The event class
            handler_type: The handler class
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        if handler_type not in self._event_handlers[event_type]:
            self._event_handlers[event_type].append(handler_type)

    def discover(self, module_path: str, recursive: bool = True) -> int:
        """Discover handlers from a module or package.

        Scans the module for classes that inherit from handler base classes
        and registers them automatically.

        Args:
            module_path: Python module path (e.g., "app.handlers")
            recursive: Whether to scan submodules

        Returns:
            Number of handlers discovered
        """
        if module_path in self._discovered_modules:
            return 0

        self._discovered_modules.add(module_path)
        discovered = 0

        try:
            module = importlib.import_module(module_path)
        except ImportError:
            return 0

        # Scan module for handler classes
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if self._is_handler_class(obj):
                discovered += self._register_handler_class(obj)

        # Recursively scan submodules
        if recursive and hasattr(module, "__path__"):
            for _, submodule_name, _ in pkgutil.iter_modules(module.__path__):
                full_path = f"{module_path}.{submodule_name}"
                discovered += self.discover(full_path, recursive=True)

        return discovered

    def _is_handler_class(self, cls: type) -> bool:
        """Check if a class is a handler."""
        if not inspect.isclass(cls):
            return False

        # Skip abstract base classes
        if cls in (
            CommandHandlerProtocol,
            QueryHandlerProtocol,
            EventHandlerProtocol,
            MultiEventHandlerProtocol,
        ):
            return False

        return issubclass(
            cls,
            (
                CommandHandlerProtocol,
                QueryHandlerProtocol,
                EventHandlerProtocol,
                MultiEventHandlerProtocol,
            ),
        ) and not inspect.isabstract(cls)

    def _register_handler_class(self, handler_class: type) -> int:
        """Register a handler class based on its type."""
        registered = 0

        # Check for explicit handler markers
        if hasattr(handler_class, "_handles_command"):
            command_type = handler_class._handles_command
            self.register_command_handler(command_type, handler_class)
            registered += 1

        if hasattr(handler_class, "_handles_query"):
            query_type = handler_class._handles_query
            self.register_query_handler(query_type, handler_class)
            registered += 1

        if hasattr(handler_class, "_handles_events"):
            for event_type in handler_class._handles_events:
                self.register_event_handler(event_type, handler_class)
                registered += 1

        # Try to infer from Generic type parameters
        if registered == 0:
            registered += self._infer_handler_type(handler_class)

        return registered

    def _infer_handler_type(self, handler_class: type) -> int:
        """Try to infer handler type from class hierarchy."""
        # Get the original bases to find Generic parameters
        orig_bases = getattr(handler_class, "__orig_bases__", [])

        for base in orig_bases:
            # Check if it's a parameterized generic
            origin = getattr(base, "__origin__", None)
            args = getattr(base, "__args__", ())

            if not args:
                continue

            if origin is CommandHandlerProtocol and len(args) >= 1:
                self.register_command_handler(args[0], handler_class)
                return 1

            if origin is QueryHandlerProtocol and len(args) >= 1:
                self.register_query_handler(args[0], handler_class)
                return 1

            if origin is EventHandlerProtocol and len(args) >= 1:
                self.register_event_handler(args[0], handler_class)
                return 1

        return 0

    def register_with_buses(
        self,
        command_bus: CommandBusProtocol | None = None,
        query_bus: QueryBusProtocol | None = None,
        event_bus: EventBusProtocol | None = None,
        handler_factory: Callable[[type], Any] | None = None,
    ) -> None:
        """Register all discovered handlers with buses.

        Args:
            command_bus: Command bus to register with
            query_bus: Query bus to register with
            event_bus: Event bus to register with
            handler_factory: Factory function to instantiate handlers
        """
        if command_bus:
            for cmd_type, cmd_handler_type in self._command_handlers.items():
                if isinstance(cmd_handler_type, type):
                    handler = (
                        handler_factory(cmd_handler_type)
                        if handler_factory
                        else cmd_handler_type()
                    )
                else:
                    handler = cmd_handler_type
                # Cast to expected Bus register signature to satisfy static typing
                from typing import cast

                command_bus.register(  # type: ignore[attr-defined]
                    cmd_type,
                    cast("Callable[[type], Any] | type", handler),
                )

        if query_bus:
            for qry_type, qry_handler_type in self._query_handlers.items():
                if isinstance(qry_handler_type, type):
                    handler = (
                        handler_factory(qry_handler_type)
                        if handler_factory
                        else qry_handler_type()
                    )
                else:
                    handler = qry_handler_type
                from typing import cast

                query_bus.register(  # type: ignore[attr-defined]
                    qry_type,
                    cast("Callable[[type], Any] | type", handler),
                )

        if event_bus:
            for evt_type, handler_types in self._event_handlers.items():
                for evt_handler_type in handler_types:
                    if isinstance(evt_handler_type, type):
                        handler = (
                            handler_factory(evt_handler_type)
                            if handler_factory
                            else evt_handler_type()
                        )
                    else:
                        handler = evt_handler_type
                    from typing import cast

                    event_bus.subscribe(
                        evt_type,
                        cast("Callable[[type], Any] | type", handler),
                    )

    def get_command_handlers(
        self,
    ) -> dict[type, type[CommandHandlerProtocol[Any, Any]]]:
        """Get all registered command handlers."""
        return dict(self._command_handlers.items())

    def get_query_handlers(self) -> dict[type, type[QueryHandlerProtocol[Any, Any]]]:
        """Get all registered query handlers."""
        return dict(self._query_handlers.items())

    def get_event_handlers(self) -> dict[type, list[type[EventHandlerProtocol[Any]]]]:
        """Get all registered event handlers."""
        return {k: list(v) for k, v in self._event_handlers.items()}


def clear_handler_registry() -> None:
    """Clear all registered handlers from the global handler registry.

    Intended for use in tests to reset handler state between test runs.
    Clears both the HandlerRegistry instances and the global decorator registry.
    """
    from quadkit.events.decorators.handlers import clear_handlers

    clear_handlers()


__all__ = ["HandlerRegistry", "clear_handler_registry"]
