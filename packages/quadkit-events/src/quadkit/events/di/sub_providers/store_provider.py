"""Sub-provider for AbstractEventStore and AbstractSnapshotStore creation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from quadkit.contracts.core.di import (
        ContainerRegistrarProtocol,
        ContainerResolverProtocol,
    )
    from quadkit.events.config import EventsConfig
    from quadkit.events.stores.registry import EventStoreRegistry


class StoreSubProvider:
    """Focused sub-provider: creates and owns AbstractEventStore + AbstractSnapshotStore."""

    def __init__(
        self,
        config: EventsConfig,
        registry: EventStoreRegistry | None = None,
    ) -> None:
        from quadkit.events.stores.registry import EventStoreRegistry as _Registry
        from quadkit.logging import get_logger

        self._logger = get_logger(__name__)
        self._config = config
        self._registry = registry or _Registry.with_defaults()
        self.event_store: Any = None
        self.snapshot_store: Any = None
        self.snapshot_manager: Any = None
        self._deferred_container: Any = None

    def _can_defer_creation(
        self,
        backend_key: str,
        container: ContainerRegistrarProtocol | None,
    ) -> bool:
        """Return True if *backend_key* depends on a sibling provider not yet registered."""
        if container is None or not hasattr(container, "has"):
            return False
        if backend_key == "postgres":
            from quadkit.contracts.data.sql.database import DatabaseProviderProtocol

            return not bool(container.has(DatabaseProviderProtocol))
        if backend_key == "mongodb":
            from quadkit.contracts.data import DocumentStoreProtocol

            return not bool(container.has(DocumentStoreProtocol))
        return False

    def _configure_snapshots(self, backend_key: str) -> None:
        """Initialise snapshot store/manager once ``self.event_store`` exists."""
        from quadkit.events.constants import StoreType
        from quadkit.events.stores import InMemorySnapshotStore, SnapshotManager
        from quadkit.events.types import EventStoreBackend

        snapshots_config = self._config.snapshots
        if isinstance(snapshots_config, dict):
            self._logger.debug(
                "snapshots_skipped", reason="dict_config_not_fully_typed"
            )
        elif snapshots_config and snapshots_config.enabled:
            memory_snapshots_enabled = True
            if backend_key in (StoreType.MEMORY, EventStoreBackend.MEMORY.value):
                memory_snapshots_enabled = self._config.memory.enable_snapshots
            if memory_snapshots_enabled and self.snapshot_manager is None:
                self.snapshot_store = InMemorySnapshotStore()
                self.snapshot_manager = SnapshotManager(
                    event_store=self.event_store,
                    snapshot_store=self.snapshot_store,
                    config=snapshots_config,
                )

    async def _build_store(self, container: Any) -> Any:
        """Instantiate ``self.event_store`` from ``self._registry``."""
        backend_key = self._config.event_store_backend.value
        try:
            factory_container = cast("ContainerResolverProtocol | None", container)
            self.event_store = await self._registry.create(
                backend_key, self._config, factory_container
            )
        except KeyError as exc:
            raise ValueError(f"Unknown event store backend: {backend_key!r}") from exc
        except Exception as exc:  # noqa: BLE001 — infrastructure init; unknown backend factory failure; logs and re-raises
            self._logger.error(
                "events.store_creation_failed",
                store_type=backend_key,
                error=str(exc),
                exc_info=True,
            )
            raise

        self._deferred_container = None
        self._configure_snapshots(backend_key)
        return self.event_store

    async def _resolve_deferred_store(self) -> Any:
        """Lazy singleton factory invoked when store creation was deferred at register()."""
        if self.event_store is not None:
            return self.event_store
        return await self._build_store(self._deferred_container)

    async def ensure_store(self, container: ContainerResolverProtocol) -> Any:
        """Materialize a deferred store during ``boot()`` once infrastructure is registered."""
        if self.event_store is not None:
            return self.event_store
        backend_key = self._config.event_store_backend.value
        if self._can_defer_creation(backend_key, cast("Any", container)):
            return None
        return await self._build_store(container)

    async def setup(self, container: ContainerRegistrarProtocol | None = None) -> None:
        """Create all stores based on configuration (or defer until boot when DB isn't registered yet)."""
        backend_key = self._config.event_store_backend.value
        if self._can_defer_creation(backend_key, container):
            self._deferred_container = container
            return

        await self._build_store(container)

    async def teardown(self) -> None:
        """Close store connections."""
        if self.event_store and hasattr(self.event_store, "close"):
            await self.event_store.close()
        if self.snapshot_store and hasattr(self.snapshot_store, "close"):
            await self.snapshot_store.close()

    def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register stores into the DI container."""
        from quadkit.contracts.events import EventStoreProtocol, SnapshotStoreProtocol
        from quadkit.events.stores import (
            AbstractEventStore,
            AbstractSnapshotStore,
            SnapshotManager,
        )

        if self.event_store:
            container.singleton(cast("Any", AbstractEventStore), self.event_store)
            container.singleton(cast("Any", EventStoreProtocol), self.event_store)
        elif self._deferred_container is not None:
            container.singleton(
                cast("Any", AbstractEventStore),
                factory=self._resolve_deferred_store,
            )
            container.singleton(
                cast("Any", EventStoreProtocol),
                factory=self._resolve_deferred_store,
            )
        if self.snapshot_store:
            container.singleton(cast("Any", AbstractSnapshotStore), self.snapshot_store)
            container.singleton(cast("Any", SnapshotStoreProtocol), self.snapshot_store)
        if self.snapshot_manager:
            container.singleton(cast("Any", SnapshotManager), self.snapshot_manager)


__all__ = ["StoreSubProvider"]
