"""Sub-provider for handler discovery and wiring (M-01)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol
    from quadkit.events.config import EventsConfig

T = TypeVar("T")


class HandlerSubProvider:
    """Focused sub-provider: discovers and wires command/query/event handlers.

    Example::

        sub = HandlerSubProvider(
            config,
            handler_modules=["my_app.handlers"],
            command_bus=bus,
            query_bus=qbus,
            event_bus=ebus,
        )
        await sub.setup(container)
    """

    def __init__(
        self,
        config: EventsConfig,
        handler_modules: list[str],
        command_bus: Any = None,
        query_bus: Any = None,
        event_bus: Any = None,
    ) -> None:
        self._config = config
        self._handler_modules = handler_modules
        self._command_bus = command_bus
        self._query_bus = query_bus
        self._event_bus = event_bus
        self.handler_registry: Any = None

    async def setup(self, container: ContainerResolverProtocol) -> None:
        """Discover handlers and wire them to buses.

        All handler types are resolved eagerly via ``await container.resolve()``
        before being registered with the buses.  This avoids both capturing
        the container in a long-lived closure and the silent bug of returning
        a coroutine object instead of a handler instance (which would happen
        if ``container.resolve`` were called without ``await`` inside a sync
        factory).
        """
        from typing import cast

        from quadkit.events.handlers import HandlerRegistry

        self.handler_registry = HandlerRegistry()

        for module in self._handler_modules:
            self.handler_registry.discover(module)

        # Collect every unique handler *type* from all three registries.
        all_handler_types: set[type] = set()
        for handler_type in self.handler_registry.get_command_handlers().values():
            if isinstance(handler_type, type):
                all_handler_types.add(handler_type)
        for handler_type in self.handler_registry.get_query_handlers().values():
            if isinstance(handler_type, type):
                all_handler_types.add(handler_type)
        for handler_types in self.handler_registry.get_event_handlers().values():
            for handler_type in handler_types:
                if isinstance(handler_type, type):
                    all_handler_types.add(handler_type)

        # Eagerly resolve each handler instance via the container.
        # Using ``await`` here is correct — ``ContainerResolverProtocol.resolve`` is
        # an async method and must not be called without ``await``.
        resolved: dict[type, Any] = {}
        for handler_type in all_handler_types:
            resolved[handler_type] = await container.resolve(handler_type)

        def handler_factory(handler_type: type[T]) -> T:
            """Look up a pre-resolved handler instance."""
            return cast("T", resolved[handler_type])

        self.handler_registry.register_with_buses(
            command_bus=self._command_bus,
            query_bus=self._query_bus,
            event_bus=self._event_bus,
            handler_factory=handler_factory,
        )


__all__ = ["HandlerSubProvider"]
