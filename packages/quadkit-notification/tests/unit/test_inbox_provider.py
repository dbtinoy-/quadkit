"""Unit tests for InboxProvider registration and health-check delegation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.core import HealthCheckResult, HealthStatus
from quadkit.contracts.notification.inbox import InboxStoreProtocol
from quadkit.notification.config import InboxConfig
from quadkit.notification.di.inbox_provider import InboxProvider
from quadkit.notification.inbox.service import InboxService


class FakeRegistrar:
    """Records singleton registrations for assertions."""

    def __init__(self) -> None:
        self.registrations: list[tuple[object, object | None, object | None]] = []

    def singleton(
        self,
        service_type: object,
        instance: object | None = None,
        *,
        name: str | None = None,
        factory: object | None = None,
        validate: bool = True,
    ) -> None:
        self.registrations.append((service_type, instance, factory))


class TestInboxProviderRegistration:
    """Unit tests for backend selection at registration time."""

    @pytest.mark.asyncio
    async def test_memory_backend_registers_in_memory_store(self) -> None:
        from quadkit.notification.inbox.memory import InMemoryInboxStore

        provider = InboxProvider(config=InboxConfig(store_backend="memory"))
        registrar = FakeRegistrar()

        await provider.register(registrar)  # type: ignore[arg-type]

        bindings = {
            st: (inst, factory) for st, inst, factory in registrar.registrations
        }
        store_impl, store_factory = bindings[InboxStoreProtocol]
        assert store_impl is InMemoryInboxStore
        assert store_factory is None
        assert InboxService in bindings

    @pytest.mark.asyncio
    async def test_database_backend_registers_lazy_factory(self) -> None:

        provider = InboxProvider(config=InboxConfig(store_backend="database"))
        registrar = FakeRegistrar()

        await provider.register(registrar)  # type: ignore[arg-type]

        bindings = {
            st: (inst, factory) for st, inst, factory in registrar.registrations
        }
        store_impl, store_factory = bindings[InboxStoreProtocol]
        assert store_impl is None
        assert callable(store_factory)
        assert store_factory.__name__ == "_database_store_factory"

    @pytest.mark.asyncio
    async def test_database_factory_builds_database_store(self) -> None:
        from quadkit.contracts.data.sql.database import (
            DatabaseProviderProtocol,
        )

        provider = InboxProvider(config=InboxConfig(store_backend="database"))
        registrar = FakeRegistrar()
        await provider.register(registrar)  # type: ignore[arg-type]

        db = MagicMock(spec=DatabaseProviderProtocol)
        resolver = MagicMock()
        resolver.resolve = AsyncMock(return_value=db)

        bindings = {
            st: (inst, factory) for st, inst, factory in registrar.registrations
        }
        store = await bindings[InboxStoreProtocol][1](resolver)  # type: ignore[misc]
        from quadkit.notification.inbox.database import DatabaseInboxStore

        assert isinstance(store, DatabaseInboxStore)
        resolver.resolve.assert_awaited_once_with(DatabaseProviderProtocol)


class TestInboxProviderHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_degraded_before_boot(self) -> None:
        provider = InboxProvider()

        result = await provider.health_check()

        assert result.component == "inbox"
        assert result.status == HealthStatus.DEGRADED
        assert result.message == "inbox store not initialized"

    @pytest.mark.asyncio
    async def test_health_check_delegates_to_store_after_boot(self) -> None:
        provider = InboxProvider()
        store = MagicMock(spec=InboxStoreProtocol)
        store_health = HealthCheckResult(
            component="inbox_store",
            status=HealthStatus.HEALTHY,
            message="store healthy",
            details={"backend": "memory"},
            duration_ms=12.0,
        )
        store.health_check = AsyncMock(return_value=store_health)

        service = InboxService(store=store)

        async def resolve(dep: object) -> object:
            if dep is InboxService:
                return service
            if dep is InboxStoreProtocol:
                return store
            raise AssertionError(f"Unexpected resolve target: {dep!r}")

        container = MagicMock()
        container.resolve = AsyncMock(side_effect=resolve)

        await provider.boot(container)

        result = await provider.health_check(timeout=2.0)

        assert result.component == "inbox"
        assert result.status == store_health.status
        assert result.message == store_health.message
        assert result.details == store_health.details
        assert result.error is store_health.error
        assert result.duration_ms == store_health.duration_ms
        store.health_check.assert_awaited_once_with(timeout=2.0)
