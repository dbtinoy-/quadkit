from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from quadkit.events.stores.base import AbstractEventStore
from quadkit.logging import get_logger

if TYPE_CHECKING:
    from quadkit.contracts.core.di import ContainerResolverProtocol
    from quadkit.events.config import EventsConfig

logger = get_logger(__name__)

# Type alias for store factory callables (async-first: factories may resolve
# their infrastructure dependencies from the container)
_StoreFactoryCallable = Callable[..., Awaitable[AbstractEventStore]]


class EventStoreRegistry:
    """Registry that maps EventStoreBackend keys to async store factories.

    Provides a clean alternative to if/elif chains for store dispatch.
    Factories are async callables that accept (config, container) and
    return an AbstractEventStore.

    Usage::

        registry = EventStoreRegistry.with_defaults()
        store = await registry.create("postgres", config, container)
    """

    def __init__(self) -> None:
        """Initialize with an empty registry."""
        self._factories: dict[str, _StoreFactoryCallable] = {}

    @classmethod
    def _default_entries(cls) -> dict[str, _StoreFactoryCallable]:
        """Declare the built-in store factories (memory, postgres, mongodb, sqlite)."""
        from quadkit.events.stores.registry_factories import (
            create_inmemory_store,
            create_mongodb_store,
            create_postgres_store,
            create_sqlite_store,
        )

        return {
            "memory": create_inmemory_store,
            "postgres": create_postgres_store,
            "mongodb": create_mongodb_store,
            "sqlite": create_sqlite_store,
        }

    @classmethod
    def with_defaults(cls) -> EventStoreRegistry:
        """Create a registry pre-populated with all built-in store factories."""
        registry = cls()
        for key, value in cls._default_entries().items():
            registry.register(key, value)
        return registry

    def register(self, key: str, factory: _StoreFactoryCallable) -> None:
        """Register a store factory under the given backend key.

        Args:
            key: The EventStoreBackend value string (e.g., 'postgres').
            factory: Callable(config, container) -> AbstractEventStore.
        """
        self._factories[key] = factory

    async def create(
        self,
        key: str,
        config: EventsConfig,
        container: ContainerResolverProtocol | None,
    ) -> AbstractEventStore:
        """Create a store for the given backend key.

        Args:
            key: The EventStoreBackend value string.
            config: The EventsConfig instance.
            container: The DI container resolver; factories that resolve
                infrastructure from it require it to be present.

        Returns:
            An AbstractEventStore instance.

        Raises:
            KeyError: If no factory is registered for the given key.
        """
        factory = self._factories.get(key)
        if factory is None:
            available = list(self._factories.keys())
            raise KeyError(
                f"No store factory registered for backend '{key}'. "
                f"Available: {available}"
            )
        logger.debug("creating_event_store", backend=key)
        store: AbstractEventStore = await factory(config, container)
        return store

    def keys(self) -> list[str]:
        """Return all registered backend keys.

        Returns:
            List of registered backend key strings.
        """
        return list(self._factories.keys())
