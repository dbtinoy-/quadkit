"""Unit tests for events sub-providers (StoreSubProvider, BusSubProvider, HandlerSubProvider, ManagerSubProvider)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.events.config import EventsConfig
from quadkit.events.di.sub_providers.bus_provider import BusSubProvider
from quadkit.events.di.sub_providers.handler_provider import HandlerSubProvider
from quadkit.events.di.sub_providers.manager_provider import ManagerSubProvider
from quadkit.events.di.sub_providers.store_provider import StoreSubProvider


class _DummyContainer:
    """Minimal container mock for sub-provider registration."""

    def __init__(self) -> None:
        self.bindings: dict[type, object] = {}

    def singleton(self, contract: type, implementation: object) -> None:
        self.bindings[contract] = implementation

    def has(self, contract: type) -> bool:
        return contract in self.bindings


class TestBusSubProvider:
    """Tests for BusSubProvider."""

    def test_bus_subprovider_instantiation(self) -> None:
        """Verify BusSubProvider can be instantiated."""
        config = EventsConfig()
        sub = BusSubProvider(config)
        assert sub is not None
        assert sub._config is config

    @pytest.mark.asyncio
    async def test_bus_subprovider_setup_creates_buses(self) -> None:
        """Verify setup() creates all three buses."""
        config = EventsConfig()
        sub = BusSubProvider(config)
        await sub.setup()

        assert sub.command_bus is not None
        assert sub.query_bus is not None
        assert sub.event_bus is not None

    @pytest.mark.asyncio
    async def test_bus_subprovider_boot_calls_start(self) -> None:
        """Verify boot() calls start() on buses that support it."""
        config = EventsConfig()
        sub = BusSubProvider(config)
        await sub.setup()

        sub.command_bus.start = AsyncMock()
        sub.query_bus.start = AsyncMock()
        sub.event_bus.start = AsyncMock()

        await sub.boot()

        sub.command_bus.start.assert_awaited_once()
        sub.query_bus.start.assert_awaited_once()
        sub.event_bus.start.assert_awaited_once()

    def test_bus_subprovider_set_tracer(self) -> None:
        """Verify set_tracer() wires tracer into event bus."""
        config = EventsConfig()
        sub = BusSubProvider(config)

        sub.event_bus = MagicMock()
        sub.event_bus.set_tracer = MagicMock()

        tracer = object()
        sub.set_tracer(tracer)

        sub.event_bus.set_tracer.assert_called_once_with(tracer)

    def test_bus_subprovider_set_hook_registry(self) -> None:
        """Verify set_hook_registry() wires hooks into event bus."""
        config = EventsConfig()
        sub = BusSubProvider(config)

        sub.event_bus = MagicMock()
        sub.event_bus.set_hook_registry = MagicMock()

        hooks = object()
        sub.set_hook_registry(hooks)

        sub.event_bus.set_hook_registry.assert_called_once_with(hooks)
        assert sub._hooks is hooks

    def test_bus_subprovider_register_binds_buses(self) -> None:
        """Verify register() binds buses to container."""
        config = EventsConfig()
        sub = BusSubProvider(config)

        container = _DummyContainer()

        sub.command_bus = MagicMock()
        sub.query_bus = MagicMock()
        sub.event_bus = MagicMock()

        sub.register(container)

        assert len(container.bindings) > 0

    @pytest.mark.asyncio
    async def test_bus_subprovider_health_check(self) -> None:
        """Verify health_check() returns health result."""
        config = EventsConfig()
        sub = BusSubProvider(config)
        await sub.setup()

        sub.command_bus.health_check = AsyncMock(return_value=MagicMock(status="healthy"))

        result = await sub.health_check()

        assert result is not None


class TestStoreSubProvider:
    """Tests for StoreSubProvider."""

    def test_store_subprovider_instantiation(self) -> None:
        """Verify StoreSubProvider can be instantiated."""
        config = EventsConfig()
        sub = StoreSubProvider(config)
        assert sub is not None
        assert sub._config is config

    def test_store_subprovider_with_registry(self) -> None:
        """Verify StoreSubProvider accepts custom registry."""
        from quadkit.events.stores.registry import EventStoreRegistry

        config = EventsConfig()
        registry = EventStoreRegistry.with_defaults()
        sub = StoreSubProvider(config, registry=registry)
        assert sub._registry is registry

    @pytest.mark.asyncio
    async def test_store_subprovider_setup_creates_event_store(self) -> None:
        """Verify setup() creates event store with memory backend."""
        config = EventsConfig()
        sub = StoreSubProvider(config)
        container = MagicMock()

        await sub.setup(container)

        assert sub.event_store is not None

    @pytest.mark.asyncio
    async def test_store_subprovider_setup_creates_snapshot_manager(self) -> None:
        """Verify setup() creates snapshot manager when enabled."""
        config = EventsConfig(snapshots={"enabled": True})
        sub = StoreSubProvider(config)
        container = MagicMock()

        await sub.setup(container)

        assert sub.snapshot_manager is not None

    @pytest.mark.asyncio
    async def test_store_subprovider_teardown_closes_stores(self) -> None:
        """Verify teardown() closes store connections."""
        config = EventsConfig()
        sub = StoreSubProvider(config)

        mock_store = AsyncMock()
        sub.event_store = mock_store
        sub.snapshot_store = AsyncMock()

        await sub.teardown()

        mock_store.close.assert_awaited_once()

    def test_store_subprovider_register_binds_stores(self) -> None:
        """Verify register() binds stores to container."""
        config = EventsConfig()
        sub = StoreSubProvider(config)

        container = _DummyContainer()
        sub.event_store = MagicMock()

        sub.register(container)

        assert len(container.bindings) > 0

    def test_register_binds_the_snapshot_protocol_it_exports(self) -> None:
        """`SnapshotStoreProtocol` must be bound, not only the abstract base.

        `EventsModule.configure()` exports the protocol, so a consumer that
        injects it reads this binding. Registering the store under
        `AbstractSnapshotStore` and `SnapshotManager` alone left the exported
        protocol unresolvable (`QK_ERR_DI_004`) while the store sat in the
        container — and nothing noticed, because no test and no consumer in
        the package resolved the protocol.
        """
        from quadkit.contracts.events import SnapshotStoreProtocol
        from quadkit.events.stores import InMemorySnapshotStore

        sub = StoreSubProvider(EventsConfig())
        snapshot_store = InMemorySnapshotStore()
        sub.snapshot_store = snapshot_store
        container = _DummyContainer()

        sub.register(container)

        bound = container.bindings[SnapshotStoreProtocol]
        assert bound is snapshot_store
        # Conformance matters: the container rejects a non-conforming binding
        # at registration (QK_ERR_DI_007), so this is what makes the export
        # resolvable in a real container.
        assert isinstance(bound, SnapshotStoreProtocol)

    @pytest.mark.asyncio
    async def test_memory_backend_registers_a_conforming_snapshot_store(self) -> None:
        """The full setup → register path with the memory backend."""
        from quadkit.contracts.events import SnapshotStoreProtocol

        sub = StoreSubProvider(EventsConfig())
        await sub.setup(None)
        container = _DummyContainer()

        sub.register(container)

        assert SnapshotStoreProtocol in container.bindings
        assert isinstance(
            container.bindings[SnapshotStoreProtocol], SnapshotStoreProtocol
        )


class TestHandlerSubProvider:
    """Tests for HandlerSubProvider."""

    def test_handler_subprovider_instantiation(self) -> None:
        """Verify HandlerSubProvider can be instantiated."""
        config = EventsConfig()
        sub = HandlerSubProvider(config, handler_modules=[])
        assert sub is not None
        assert sub._config is config

    def test_handler_subprovider_with_buses(self) -> None:
        """Verify HandlerSubProvider accepts bus instances."""
        config = EventsConfig()
        cmd_bus = MagicMock()
        qry_bus = MagicMock()
        evt_bus = MagicMock()

        sub = HandlerSubProvider(
            config,
            handler_modules=[],
            command_bus=cmd_bus,
            query_bus=qry_bus,
            event_bus=evt_bus,
        )
        assert sub._command_bus is cmd_bus
        assert sub._query_bus is qry_bus
        assert sub._event_bus is evt_bus

    @pytest.mark.asyncio
    async def test_handler_subprovider_setup_creates_registry(self) -> None:
        """Verify setup() creates handler registry."""
        config = EventsConfig()
        sub = HandlerSubProvider(config, handler_modules=[])
        container = MagicMock()

        await sub.setup(container)

        assert sub.handler_registry is not None


class TestManagerSubProvider:
    """Tests for ManagerSubProvider."""

    def test_manager_subprovider_instantiation(self) -> None:
        """Verify ManagerSubProvider can be instantiated."""
        config = EventsConfig()
        sub = ManagerSubProvider(config)
        assert sub is not None
        assert sub._config is config

    def test_manager_subprovider_with_event_store(self) -> None:
        """Verify ManagerSubProvider accepts event store."""
        config = EventsConfig()
        store = MagicMock()

        sub = ManagerSubProvider(config, event_store=store)
        assert sub._event_store is store

    @pytest.mark.asyncio
    async def test_manager_subprovider_setup_creates_managers(self) -> None:
        """Verify setup() creates projection and saga managers."""
        config = EventsConfig()
        sub = ManagerSubProvider(config)

        await sub.setup()

        assert sub.projection_manager is not None
        assert sub.saga_manager is not None

    @pytest.mark.asyncio
    async def test_manager_subprovider_boot_calls_start(self) -> None:
        """Verify boot() calls start() on projection manager."""
        config = EventsConfig()
        sub = ManagerSubProvider(config)
        await sub.setup()

        sub.projection_manager.start = AsyncMock()

        await sub.boot()

        sub.projection_manager.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_manager_subprovider_teardown_calls_stop(self) -> None:
        """Verify teardown() calls stop() on projection manager."""
        config = EventsConfig()
        sub = ManagerSubProvider(config)
        await sub.setup()

        sub.projection_manager.stop = AsyncMock()

        await sub.teardown()

        sub.projection_manager.stop.assert_awaited_once()

    def test_manager_subprovider_register_binds_managers(self) -> None:
        """Verify register() binds managers to container."""
        config = EventsConfig()
        sub = ManagerSubProvider(config)

        container = _DummyContainer()
        sub.projection_manager = MagicMock()

        sub.register(container)

        assert len(container.bindings) > 0
