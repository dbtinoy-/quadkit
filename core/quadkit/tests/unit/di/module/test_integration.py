# file: tests/di/module/test_integration.py
"""End-to-end integration tests — full Application boot with modules."""

from __future__ import annotations

import pytest

from quadkit.app.base import AppState, Application
from quadkit.config.main import QuadkitConfig
from quadkit.contracts.core.di import ContainerRegistrarProtocol, ContainerResolverProtocol
from quadkit.contracts.core.health import AggregateHealthResult
from quadkit.di.module import DynamicModule, Module, global_module, module
from quadkit.di.provider import Provider, ProviderPriority


# ---------------------------------------------------------------------------
# Test protocols (fake contracts)
# ---------------------------------------------------------------------------


class DatabaseSession:
    """Fake database session protocol."""


class CacheBackendProtocol:
    """Fake cache backend protocol."""


class AuthServiceProtocol:
    """Fake auth service protocol."""


class OrderServiceProtocol:
    """Fake order service protocol."""


# ---------------------------------------------------------------------------
# Test providers
# ---------------------------------------------------------------------------


class DbProvider(Provider):
    name = "db"
    priority = ProviderPriority.INFRASTRUCTURE
    provides = [DatabaseSession]

    def __init__(self, url: str = "sqlite:///test.db"):
        super().__init__()
        self.url = url

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        container.singleton(DatabaseSession, DatabaseSession)


class CacheProvider(Provider):
    name = "cache"
    priority = ProviderPriority.INFRASTRUCTURE
    provides = [CacheBackendProtocol]

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        container.singleton(CacheBackendProtocol, CacheBackendProtocol)


class AuthProvider(Provider):
    name = "auth"
    priority = ProviderPriority.SECURITY
    provides = [AuthServiceProtocol]

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        container.singleton(AuthServiceProtocol, AuthServiceProtocol)


class OrderProvider(Provider):
    name = "orders"
    priority = ProviderPriority.DOMAIN
    provides = [OrderServiceProtocol]

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        container.singleton(OrderServiceProtocol, OrderServiceProtocol)


# ---------------------------------------------------------------------------
# Test modules
# ---------------------------------------------------------------------------


@module()
class InfraModule(Module):
    @classmethod
    def configure(cls, db_url: str = "sqlite:///test.db") -> DynamicModule:
        return DynamicModule(
            module=cls,
            providers=[DbProvider(url=db_url), CacheProvider()],
            exports=[DatabaseSession, CacheBackendProtocol],
            is_global=True,
        )


@module(
    providers=[AuthProvider],
    exports=[AuthServiceProtocol],
)
class AuthModule:
    pass


@module(
    imports=[AuthModule],
    providers=[OrderProvider],
    exports=[OrderServiceProtocol],
)
class OrderModule:
    pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFullApplicationBoot:
    """Test complete application lifecycle with modules."""

    @pytest.mark.asyncio
    async def test_boot_with_modules(self):
        async with Application.boot(
            name="test-app",
            modules=[
                InfraModule.configure(db_url="sqlite:///test.db"),
                AuthModule,
                OrderModule,
            ],
        ) as app:
            assert app.state == AppState.RUNNING

            # All services should be resolvable
            db = await app.container.resolve(DatabaseSession)
            assert isinstance(db, DatabaseSession)

            cache = await app.container.resolve(CacheBackendProtocol)
            assert isinstance(cache, CacheBackendProtocol)

            auth = await app.container.resolve(AuthServiceProtocol)
            assert isinstance(auth, AuthServiceProtocol)

            orders = await app.container.resolve(OrderServiceProtocol)
            assert isinstance(orders, OrderServiceProtocol)

        assert app.state == AppState.STOPPED

    @pytest.mark.asyncio
    async def test_boot_with_modules_and_standalone(self):
        """Test mixing modules and standalone providers."""

        class StandaloneMetrics(Provider):
            name = "metrics"
            priority = ProviderPriority.LOW

            async def register(self, container: ContainerRegistrarProtocol) -> None:
                pass

        async with Application.boot(
            name="test-app",
            modules=[InfraModule.configure()],
            providers=[StandaloneMetrics()],
        ) as app:
            assert app.state == AppState.RUNNING
            assert len(app.providers) >= 3  # 2 from InfraModule + 1 standalone

    @pytest.mark.asyncio
    async def test_module_provider_order(self):
        """Imported module providers should register before importers."""
        registration_order: list[str] = []

        class TrackingAuth(Provider):
            name = "auth"
            provides = [AuthServiceProtocol]

            async def register(self, container: ContainerRegistrarProtocol) -> None:
                registration_order.append("auth")
                container.singleton(AuthServiceProtocol, AuthServiceProtocol)

        class TrackingOrder(Provider):
            name = "orders"
            provides = [OrderServiceProtocol]

            async def register(self, container: ContainerRegistrarProtocol) -> None:
                registration_order.append("orders")
                container.singleton(OrderServiceProtocol, OrderServiceProtocol)

        @module(providers=[TrackingAuth], exports=[AuthServiceProtocol])
        class TrackAuthModule:
            pass

        @module(
            imports=[TrackAuthModule],
            providers=[TrackingOrder],
            exports=[OrderServiceProtocol],
        )
        class TrackOrderModule:
            pass

        async with Application.boot(
            name="test-app",
            modules=[TrackOrderModule],
        ) as app:
            assert registration_order.index("auth") < registration_order.index("orders")

    @pytest.mark.asyncio
    async def test_add_module_after_start_raises(self):
        app = Application(name="test-app")

        @module()
        class MyModule:
            pass

        app.add_module(MyModule)
        await app.start()

        with pytest.raises(RuntimeError, match="Cannot add_module after boot"):
            app.add_module(MyModule)

        await app.stop()

    @pytest.mark.asyncio
    async def test_health_check_with_modules(self):
        async with Application.boot(
            name="test-app",
            modules=[InfraModule.configure()],
        ) as app:
            health = await app.health_check()
            assert isinstance(health, AggregateHealthResult)


class TestModuleBootWithClassmethod:
    """Test Application.boot() classmethod with modules parameter."""

    @pytest.mark.asyncio
    async def test_boot_classmethod_with_modules(self):
        async with Application.boot(
            name="boot-test",
            modules=[
                InfraModule.configure(),
                AuthModule,
            ],
        ) as app:
            assert app.state == AppState.RUNNING
            db = await app.container.resolve(DatabaseSession)
            assert db is not None

    @pytest.mark.asyncio
    async def test_boot_classmethod_providers_only(self):
        """Gear 2 style — providers only, no modules."""
        async with Application.boot(
            name="gear2-test",
            providers=[DbProvider(), CacheProvider()],
        ) as app:
            assert app.state == AppState.RUNNING
            db = await app.container.resolve(DatabaseSession)
            assert db is not None
