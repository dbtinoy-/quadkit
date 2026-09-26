"""Registry mapping adapter keys to async wirer callables.

Each wirer is responsible for creating, connecting, and bridging
an adapter to the event bus.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.core.di import BootContainerProtocol
    from quadkit.events.config import EventsConfig

logger = get_logger(__name__)

_AdapterWirer = Callable[
    ["EventsConfig", Any, "BootContainerProtocol"], Coroutine[Any, Any, None]
]


class AdapterRegistry:
    """Registry mapping adapter keys to async wirer callables.

    Each wirer accepts (config, event_bus, container) and is responsible
    for creating, connecting, and bridging its adapter to the event bus.

    Usage::

        registry = AdapterRegistry.with_defaults()
        await registry.wire_all(config, event_bus, container)
    """

    def __init__(self) -> None:
        """Initialize with an empty registry."""
        self._wirers: dict[str, _AdapterWirer] = {}

    @classmethod
    def _default_entries(cls) -> dict[str, _AdapterWirer]:
        """Declare the built-in adapter wirers (kafka, rabbitmq)."""
        from quadkit.events.adapters.adapter_wirers import (
            wire_kafka,
            wire_rabbitmq,
        )

        return {
            "kafka": wire_kafka,
            "rabbitmq": wire_rabbitmq,
        }

    @classmethod
    def with_defaults(cls) -> AdapterRegistry:
        """Create a registry pre-populated with built-in adapter wirers."""
        registry = cls()
        for key, value in cls._default_entries().items():
            registry.register(key, value)
        return registry

    def register(self, key: str, wirer: _AdapterWirer) -> None:
        """Register a wirer under the given adapter key.

        Args:
            key: Adapter identifier (e.g., 'kafka', 'rabbitmq').
            wirer: Async callable(config, event_bus, container).
        """
        self._wirers[key] = wirer

    async def wire_all(
        self,
        config: EventsConfig,
        event_bus: Any,
        container: BootContainerProtocol,
    ) -> None:
        """Wire all adapters whose config is present.

        For each registered key, checks if config.<key> is not None
        and calls the corresponding wirer.

        Args:
            config: The EventsConfig instance.
            event_bus: The resolved EventBusProtocol instance.
            container: The boot-phase DI container (wirers register the
                connected adapter as a singleton).
        """
        for key, wirer in self._wirers.items():
            adapter_config = getattr(config, key, None)
            if adapter_config is not None:
                logger.debug("wiring_adapter", adapter=key)
                await wirer(config, event_bus, container)

    def keys(self) -> list[str]:
        """Return all registered adapter keys."""
        return list(self._wirers.keys())
