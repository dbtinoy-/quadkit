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

    async def setup(self, container: ContainerRegistrarProtocol | None = None) -> None:
        """Create all stores based on configuration.

        The container is forwarded to store factories, which resolve their
        infrastructure dependencies (database providers) from it when present.
        """
        from quadkit.events.constants import StoreType
        from quadkit.events.stores import InMemorySnapshotStore, SnapshotManager
        from quadkit.events.types import EventStoreBackend

        backend_key = self._config.event_store_backend.value

        try:
            # Factories only resolve (never register); the runtime container
            # always provides the resolver surface alongside the registrar.
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

        snapshots_config = self._config.snapshots
        if isinstance(snapshots_config, dict):
            self._logger.debug(
                "snapshots_skipped", reason="dict_config_not_fully_typed"
            )
        elif snapshots_config and snapshots_config.enabled:
            memory_snapshots_enabled = True
            if backend_key in (StoreType.MEMORY, EventStoreBackend.MEMORY.value):
                memory_snapshots_enabled = self._config.memory.enable_snapshots
            if memory_snapshots_enabled:
                self.snapshot_store = InMemorySnapshotStore()
                self.snapshot_manager = SnapshotManager(
                    event_store=self.event_store,
                    snapshot_store=self.snapshot_store,
                    config=snapshots_config,
                )

    async def teardown(self) -> None:
        """Close store connections."""
        if self.event_store and hasattr(self.event_store, "close"):
            await self.event_store.close()
        if self.snapshot_store and hasattr(self.snapshot_store, "close"):
            await self.snapshot_store.close()

    def register(self, container: ContainerRegistrarProtocol) -> None:
        """Register stores into the DI container."""
        from typing import cast

        from quadkit.contracts.events import EventStoreProtocol, SnapshotStoreProtocol
        from quadkit.events.stores import (
            AbstractEventStore,
            AbstractSnapshotStore,
            SnapshotManager,
        )

        if self.event_store:
            container.singleton(cast("Any", AbstractEventStore), self.event_store)
            container.singleton(cast("Any", EventStoreProtocol), self.event_store)
        if self.snapshot_store:
            container.singleton(cast("Any", AbstractSnapshotStore), self.snapshot_store)
            # The protocol, not just the abstract base: `EventsModule.configure`
            # exports `SnapshotStoreProtocol`, so a consumer that injects it —
            # the documented way to read snapshots outside this package — must
            # find a binding. It was registered under `AbstractSnapshotStore`
            # and `SnapshotManager` only, which made the exported protocol
            # unresolvable (`QK_ERR_DI_004`) while the store itself sat in the
            # container.
            container.singleton(cast("Any", SnapshotStoreProtocol), self.snapshot_store)
        if self.snapshot_manager:
            container.singleton(cast("Any", SnapshotManager), self.snapshot_manager)


__all__ = ["StoreSubProvider"]
