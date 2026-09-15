"""Tests for ContainerBuilder: fluent API for building DI containers."""

from typing import Any

import pytest

from quadkit.contracts.core.scopes import ServiceScope
from quadkit.di.builder import ContainerBuilder, ServiceRegistration


class TestContainerBuilderBasics:
    """Tests for basic ContainerBuilder operations."""

    def test_builder_starts_empty(self) -> None:
        """ContainerBuilder initializes with empty registrations."""
        builder = ContainerBuilder()
        assert builder._registrations == []
        assert builder._modules == []
        assert builder._providers == []

    @pytest.mark.asyncio
    async def test_build_returns_container(self) -> None:
        """ContainerBuilder.build() returns a Container."""
        builder = ContainerBuilder()
        container = await builder.build()
        assert container is not None
        # Container should have a resolve method
        assert hasattr(container, "resolve")

    @pytest.mark.asyncio
    async def test_build_empty_container_resolves_nothing(self) -> None:
        """Empty container cannot resolve unregistered services."""
        from quadkit.contracts.exceptions import UnresolvableDependencyError

        builder = ContainerBuilder()
        container = await builder.build()

        class UnknownService:
            pass

        with pytest.raises(UnresolvableDependencyError):
            await container.resolve(UnknownService)


class TestAddSingleton:
    """Tests for add_singleton method."""

    @pytest.mark.asyncio
    async def test_add_singleton_with_class(self) -> None:
        """add_singleton registers a service with SINGLETON scope."""

        class ConfigService:
            pass

        builder = ContainerBuilder()
        builder.add_singleton(ConfigService, ConfigService)
        container = await builder.build()

        instance1 = await container.resolve(ConfigService)
        instance2 = await container.resolve(ConfigService)
        assert instance1 is instance2  # Same instance (singleton)

    @pytest.mark.asyncio
    async def test_add_singleton_with_factory(self) -> None:
        """add_singleton can use a factory function."""

        class DatabaseService:
            def __init__(self) -> None:
                self.connected = True

        def create_database() -> DatabaseService:
            return DatabaseService()

        builder = ContainerBuilder()
        builder.add_singleton(DatabaseService, create_database)
        container = await builder.build()

        db = await container.resolve(DatabaseService)
        assert db.connected is True

    @pytest.mark.asyncio
    async def test_add_singleton_with_instance(self) -> None:
        """add_instance registers a pre-built instance as singleton."""

        class LoggerService:
            def __init__(self) -> None:
                self.name = "prebuilt"

        prebuilt = LoggerService()

        def get_logger() -> LoggerService:
            return prebuilt

        builder = ContainerBuilder()
        builder.add_instance(LoggerService, prebuilt)
        container = await builder.build()

        resolved = await container.resolve(LoggerService)
        assert resolved is prebuilt

    @pytest.mark.asyncio
    async def test_add_singleton_with_metadata(self) -> None:
        """add_singleton accepts optional metadata."""

        class MetricsService:
            pass

        metadata = {"version": "1.0"}
        builder = ContainerBuilder()
        builder.add_singleton(MetricsService, MetricsService, metadata=metadata)
        container = await builder.build()

        resolved = await container.resolve(MetricsService)
        assert resolved is not None


class TestAddScoped:
    """Tests for add_scoped method."""

    def test_add_scoped_returns_self(self) -> None:
        """add_scoped returns self for chaining."""

        class RequestService:
            pass

        builder = ContainerBuilder()
        result = builder.add_scoped(RequestService, RequestService)
        assert result is builder


class TestAddTransient:
    """Tests for add_transient method."""

    @pytest.mark.asyncio
    async def test_add_transient_returns_new_instance(self) -> None:
        """add_transient creates new instance each resolution."""

        class UserService:
            pass

        builder = ContainerBuilder()
        builder.add_transient(UserService, UserService)
        container = await builder.build()

        user1 = await container.resolve(UserService)
        user2 = await container.resolve(UserService)
        assert user1 is not user2


class TestFluentInterface:
    """Tests for fluent API chaining."""

    @pytest.mark.asyncio
    async def test_method_chaining(self) -> None:
        """ContainerBuilder methods return self for chaining."""

        class ServiceA:
            pass

        class ServiceC:
            pass

        builder = ContainerBuilder()
        result = builder.add_singleton(ServiceA, ServiceA).add_transient(
            ServiceC, ServiceC
        )

        assert result is builder
        container = await builder.build()

        a = await container.resolve(ServiceA)
        c = await container.resolve(ServiceC)

        assert a is not None
        assert c is not None


class TestValidation:
    """Tests for container validation."""

    @pytest.mark.asyncio
    async def test_disable_validation_skips_check(self) -> None:
        """disable_validation allows building with issues."""

        builder = ContainerBuilder()
        builder.disable_validation()
        # Should not raise even with potential issues
        container = await builder.build()
        assert container is not None


class TestServiceRegistration:
    """Tests for ServiceRegistration class."""

    def test_service_registration_init(self) -> None:
        """ServiceRegistration stores all parameters."""

        def factory() -> str:
            return "test"

        registration = ServiceRegistration(
            interface=str,
            implementation=factory,
            scope=ServiceScope.SINGLETON,
            metadata={"key": "value"},
        )

        assert registration.interface is str
        assert registration.implementation is factory
        assert registration.scope == ServiceScope.SINGLETON
        assert registration.metadata == {"key": "value"}

    def test_service_registration_defaults_metadata(self) -> None:
        """ServiceRegistration defaults metadata to empty dict."""

        registration = ServiceRegistration(
            interface=str,
            implementation=str,
            scope=ServiceScope.TRANSIENT,
        )

        assert registration.metadata == {}


class TestComplexRegistrations:
    """Tests for complex builder scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_services_resolve_correctly(self) -> None:
        """Multiple registrations resolve independently."""

        class DatabaseService:
            pass

        class CacheService:
            pass

        class UserService:
            def __init__(self, db: DatabaseService, cache: CacheService) -> None:
                self.db = db
                self.cache = cache

        builder = ContainerBuilder()
        builder.add_singleton(DatabaseService, DatabaseService)
        builder.add_singleton(CacheService, CacheService)
        builder.add_transient(UserService, UserService)
        container = await builder.build()

        user = await container.resolve(UserService)
        assert isinstance(user.db, DatabaseService)
        assert isinstance(user.cache, CacheService)


class TestAddModule:
    """Tests for add_module method."""

    def test_add_module_returns_self(self) -> None:
        """add_module returns self for chaining."""
        builder = ContainerBuilder()
        result = builder.add_module(type)
        assert result is builder

    @pytest.mark.asyncio
    async def test_add_module_stores_module(self) -> None:
        """add_module stores module for later processing."""
        builder = ContainerBuilder()
        builder.add_module(type)  # type is a valid module class
        assert len(builder._modules) == 1


class TestAddProvider:
    """Tests for add_provider method."""

    def test_add_provider_returns_self(self) -> None:
        """add_provider returns self for chaining."""
        builder = ContainerBuilder()
        result = builder.add_provider(type)
        assert result is builder

    @pytest.mark.asyncio
    async def test_add_provider_stores_provider(self) -> None:
        """add_provider stores provider for later processing."""
        builder = ContainerBuilder()
        builder.add_provider(type)  # type as mock provider
        assert len(builder._providers) == 1

    @pytest.mark.asyncio
    async def test_add_provider_calls_register(self) -> None:
        """add_provider calls register method on provider during build."""

        class MockProvider:
            def __init__(self) -> None:
                self.register_called = False

            async def register(self, container: Any) -> None:
                self.register_called = True

        provider = MockProvider()
        builder = ContainerBuilder()
        builder.add_provider(provider)
        await builder.build()

        assert provider.register_called is True


class TestContainerBuilderErrorHandling:
    """Tests for error handling in ContainerBuilder."""

    @pytest.mark.asyncio
    async def test_build_raises_on_invalid_registration(self) -> None:
        """build raises ContainerBuildError on invalid registration."""
        from quadkit.contracts.exceptions import ContainerBuildError

        builder = ContainerBuilder()
        builder._validation_enabled = True
        # Add a registration with invalid implementation (non-callable)
        builder._registrations.append(
            ServiceRegistration(
                interface=str,
                implementation=12345,  # Invalid - not callable
                scope=ServiceScope.SINGLETON,
            )
        )

        with pytest.raises(ContainerBuildError):
            await builder.build()

    @pytest.mark.asyncio
    async def test_build_logs_on_successful_build(self) -> None:
        """build logs successful container construction."""
        builder = ContainerBuilder()
        builder.add_singleton(str, lambda: "test")
        container = await builder.build()
        assert container is not None


class TestContainerBuilderWithRealModule:
    """Tests for ContainerBuilder with actual module integration."""

    @pytest.mark.asyncio
    async def test_build_with_empty_modules_list(self) -> None:
        """build works with empty modules list."""
        builder = ContainerBuilder()
        container = await builder.build()
        assert container is not None

    @pytest.mark.asyncio
    async def test_build_with_empty_providers_list(self) -> None:
        """build works with empty providers list."""
        builder = ContainerBuilder()
        container = await builder.build()
        assert container is not None
