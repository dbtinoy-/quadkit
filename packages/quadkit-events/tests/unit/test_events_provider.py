"""Unit tests for EventsProvider."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.core.provider import ProviderPriority
from quadkit.contracts.events import (
    CommandBusProtocol,
    EventBusProtocol,
    QueryBusProtocol,
)
from quadkit.di.provider import Provider
from quadkit.events.buses import CommandBusImpl, EventBusImpl, QueryBusImpl
from quadkit.events.di.provider import EventsProvider
from quadkit.events.stores import AbstractEventStore


class _RecordingContainer:
    def __init__(self) -> None:
        self.bindings: dict[type, object] = {}
        self._existing: set[type] = set()

    def transient(self, contract: type, factory: object, **kwargs: object) -> None:
        self.bindings[contract] = factory

    def singleton(
        self, contract: type, implementation: object, **kwargs: object
    ) -> None:
        self.bindings[contract] = implementation

    def has(self, contract: type) -> bool:
        return contract in self._existing

    def override(self, contract: type, implementation: object) -> None:
        self.bindings[contract] = implementation

    async def resolve(self, contract: type) -> object:
        return None

    async def resolve_optional(self, contract: type) -> object:
        return None


class TestEventsProviderStructure:
    """Test EventsProvider class structure and attributes."""

    def test_provider_class_exists(self) -> None:
        """Verify EventsProvider class exists and can be instantiated."""
        prov = EventsProvider()
        assert prov is not None
        assert isinstance(prov, EventsProvider)

    def test_provider_name(self) -> None:
        """Verify provider has correct name attribute."""
        prov = EventsProvider()
        assert prov.name == "events"

    def test_provider_priority(self) -> None:
        """Verify provider has INFRASTRUCTURE priority."""
        prov = EventsProvider()
        assert prov.priority == ProviderPriority.INFRASTRUCTURE

    def test_provider_is_provider_subclass(self) -> None:
        """Verify EventsProvider is a proper Provider subclass."""
        assert issubclass(EventsProvider, Provider)

    def test_provider_has_required_methods(self) -> None:
        """Verify provider has all required lifecycle methods."""
        prov = EventsProvider()
        assert hasattr(prov, "register")
        assert callable(prov.register)
        assert hasattr(prov, "boot")
        assert callable(prov.boot)
        assert hasattr(prov, "shutdown")
        assert callable(prov.shutdown)


class TestEventsProviderLifecycle:
    """Test EventsProvider lifecycle methods."""

    @pytest.mark.asyncio
    async def test_register_method_signature(self) -> None:
        """Verify register() method has correct async signature."""
        prov = EventsProvider()
        container = _RecordingContainer()

        await prov.register(container)

    @pytest.mark.asyncio
    async def test_boot_method_signature(self) -> None:
        """Verify boot() method has correct async signature."""
        prov = EventsProvider()
        container = _RecordingContainer()

        await prov.register(container)
        await prov.boot(container)

    @pytest.mark.asyncio
    async def test_shutdown_method_signature(self) -> None:
        """Verify shutdown() method has correct async signature."""
        prov = EventsProvider()
        container = _RecordingContainer()

        await prov.register(container)
        await prov.shutdown()

    @pytest.mark.asyncio
    async def test_health_check_returns_json_safe_component_results(self) -> None:
        """Health aggregation serializes buses and the in-memory store."""
        prov = EventsProvider()
        container = _RecordingContainer()
        await prov.register(container)

        result = await prov.health_check()
        payload = result.to_dict()
        components = payload["details"]["components"]

        assert result.is_healthy()
        assert components["buses"]["status"] == "healthy"
        assert components["buses"]["details"]["event_bus"]["status"] == "healthy"
        assert components["event_store"]["status"] == "healthy"
        assert components["event_store"]["details"]["backend"] == "memory"

    @pytest.mark.asyncio
    async def test_register_binds_store_and_bus_contracts(self) -> None:
        """Register binds concrete components and contract-boundary protocols."""
        prov = EventsProvider()
        container = _RecordingContainer()

        await prov.register(container)

        assert AbstractEventStore in container.bindings

        assert CommandBusImpl in container.bindings
        assert QueryBusImpl in container.bindings
        assert EventBusImpl in container.bindings

        assert CommandBusProtocol in container.bindings
        assert QueryBusProtocol in container.bindings
        assert EventBusProtocol in container.bindings

    @pytest.mark.asyncio
    async def test_boot_starts_buses_snapshot_and_managers(self) -> None:
        """Boot calls downstream bus and manager startup hooks."""
        prov = EventsProvider()
        container = _RecordingContainer()

        await prov.register(container)

        prov._buses.boot = AsyncMock()
        if prov._managers is not None:
            prov._managers.boot = AsyncMock()
        if prov._stores.snapshot_manager is not None:
            prov._stores.snapshot_manager.start = AsyncMock()

        await prov.boot(container)

        prov._buses.boot.assert_awaited_once()
        if prov._managers is not None:
            prov._managers.boot.assert_awaited_once()
        if prov._stores.snapshot_manager is not None:
            prov._stores.snapshot_manager.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_boot_wires_optional_tracer_into_buses(self) -> None:
        """Boot should resolve optional tracer and wire it into buses.

        This test verifies that:
        1. EventsProvider.boot() awaits resolve_optional(TracerProtocol)
        2. The resolved tracer is passed to BusSubProvider.set_tracer(...)
        """
        from quadkit.testing.fakes import FakeTracer

        prov = EventsProvider()

        # Create a mock container that returns a tracer
        tracer = FakeTracer()

        class _TracingContainer(_RecordingContainer):
            async def resolve_optional(self, contract_type):
                from quadkit.contracts.observability.tracing import TracerProtocol

                if contract_type is TracerProtocol:
                    return tracer
                return None

        container = _TracingContainer()
        await prov.register(container)

        # Boot without mocking, so real set_tracer is called
        await prov.boot(container)

        # Verify event_bus actually has the tracer wired
        assert prov._buses.event_bus._tracer is tracer

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_boot_resolves_framework_tracing_with_visibility_bypass(self) -> None:
        """Cross-cutting tracing is visible to provider boot wiring."""
        from quadkit.contracts.observability.tracing import TracerProtocol
        from quadkit.testing.fakes import FakeTracer

        prov = EventsProvider()
        tracer = FakeTracer()
        calls: list[tuple[type, bool]] = []

        class _VisibilityAwareContainer(_RecordingContainer):
            async def resolve(self, contract_type, *, bypass_visibility=False):
                calls.append((contract_type, bypass_visibility))
                if contract_type is TracerProtocol:
                    assert bypass_visibility is True
                    return tracer
                return None

        container = _VisibilityAwareContainer()
        await prov.register(container)
        await prov.boot(container)

        assert (TracerProtocol, True) in calls
        assert prov._buses.event_bus._tracer is tracer

    @pytest.mark.asyncio
    async def test_boot_wires_optional_hook_registry_into_event_bus(self) -> None:
        """Boot resolves optional hooks and wires them into the event bus."""
        from quadkit.contracts.core import HookRegistryProtocol
        from quadkit.hooks import HookRegistry

        prov = EventsProvider()
        hooks = HookRegistry("events-test")

        class _HookingContainer(_RecordingContainer):
            async def resolve_optional(self, contract_type):
                if contract_type is HookRegistryProtocol:
                    return hooks
                return None

        container = _HookingContainer()
        await prov.register(container)

        await prov.boot(container)

        assert prov._buses.event_bus._hooks is hooks

    @pytest.mark.asyncio
    async def test_shutdown_tears_down_stores_and_managers(self) -> None:
        """Shutdown calls teardown hooks on store and manager subproviders."""
        prov = EventsProvider()
        container = _RecordingContainer()

        await prov.register(container)

        prov._stores.teardown = AsyncMock()
        if prov._managers is not None:
            prov._managers.teardown = AsyncMock()

        await prov.shutdown()

        prov._stores.teardown.assert_awaited_once()
        if prov._managers is not None:
            prov._managers.teardown.assert_awaited_once()
