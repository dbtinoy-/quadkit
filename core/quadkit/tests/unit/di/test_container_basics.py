"""Tests for DI Container core functionality: register, resolve, singleton, transient."""

from __future__ import annotations

import pytest

from quadkit.contracts.exceptions import ContainerError
from quadkit.di.container import Container


class TestContainerRegistration:
    """Tests for container registration methods."""

    @pytest.mark.asyncio
    async def test_singleton_registration_with_instance(self) -> None:
        """singleton() registers a service with an instance for singleton scope."""
        container = Container()

        class UserService:
            def __init__(self):
                self.id = "test-user"

        service = UserService()
        container.singleton(UserService, service)

        resolved1 = await container.resolve(UserService)
        resolved2 = await container.resolve(UserService)

        # Same instance returned for singleton
        assert resolved1 is resolved2
        assert resolved1.id == "test-user"

    @pytest.mark.asyncio
    async def test_singleton_registration_with_factory(self) -> None:
        """singleton() registers a service with a factory function."""
        container = Container()

        call_count = 0

        class DatabaseService:
            def __init__(self):
                nonlocal call_count
                call_count += 1
                self.id = f"db-{call_count}"

        container.singleton(
            DatabaseService,
            factory=DatabaseService,  # Pass class directly, container will instantiate
        )

        resolved1 = await container.resolve(DatabaseService)
        resolved2 = await container.resolve(DatabaseService)

        # Factory called once, same instance returned
        assert call_count == 1
        assert resolved1 is resolved2

    @pytest.mark.asyncio
    async def test_transient_registration(self) -> None:
        """transient() registers a service for new instance each resolution."""
        container = Container()

        class TokenService:
            def __init__(self):
                self.id = "token"

        container.transient(TokenService, TokenService)

        resolved1 = await container.resolve(TokenService)
        resolved2 = await container.resolve(TokenService)

        # Different instances for transient
        assert resolved1 is not resolved2

    @pytest.mark.asyncio
    async def test_singleton_with_interface_and_implementation(self) -> None:
        """singleton() binds interface to implementation."""
        container = Container()

        class UserRepository:
            pass

        class SqlUserRepository(UserRepository):
            pass

        container.singleton(UserRepository, SqlUserRepository)

        resolved = await container.resolve(UserRepository)
        assert isinstance(resolved, SqlUserRepository)

    @pytest.mark.asyncio
    async def test_transient_with_interface_and_implementation(self) -> None:
        """transient() binds interface to implementation."""
        container = Container()

        class CacheBackend:
            pass

        class InMemoryCache(CacheBackend):
            pass

        container.transient(CacheBackend, InMemoryCache)

        resolved1 = await container.resolve(CacheBackend)
        resolved2 = await container.resolve(CacheBackend)

        assert isinstance(resolved1, InMemoryCache)
        assert resolved1 is not resolved2


class TestContainerResolution:
    """Tests for container resolution."""

    @pytest.mark.asyncio
    async def test_resolve_unregistered_raises(self) -> None:
        """resolve() raises ContainerError for unregistered service."""
        container = Container()

        class UnknownService:
            pass

        with pytest.raises(ContainerError):
            await container.resolve(UnknownService)

    @pytest.mark.asyncio
    async def test_resolve_by_name_string(self) -> None:
        """resolve() can resolve by string name."""
        container = Container()

        class Logger:
            def __init__(self, name: str):
                self.name = name

        container.singleton("app.logger", Logger("app"))
        container.singleton("db.logger", Logger("db"))

        app_logger = await container.resolve("app.logger")
        db_logger = await container.resolve("db.logger")

        assert app_logger.name == "app"
        assert db_logger.name == "db"

    @pytest.mark.asyncio
    async def test_resolve_optional_dependency_missing(self) -> None:
        """resolve() returns None for optional dependency not registered."""
        container = Container()

        class OptionalService:
            pass

        class Consumer:
            def __init__(self, optional: OptionalService | None = None):
                self.optional = optional

        container.transient(Consumer, Consumer)

        consumer = await container.resolve(Consumer)
        assert consumer.optional is None


class TestContainerScopes:
    """Tests for container scopes (singleton vs transient)."""

    @pytest.mark.asyncio
    async def test_singleton_returns_same_instance(self) -> None:
        """Singleton scope returns the same instance across resolutions."""
        container = Container()

        class Counter:
            def __init__(self):
                self.value = 0

        container.singleton(Counter, Counter())

        c1 = await container.resolve(Counter)
        c2 = await container.resolve(Counter)

        c1.value = 42
        assert c2.value == 42  # Same instance

    @pytest.mark.asyncio
    async def test_transient_returns_new_instance(self) -> None:
        """Transient scope returns new instance each resolution."""
        container = Container()

        class Counter:
            def __init__(self):
                self.value = 0

        container.transient(Counter, Counter)

        c1 = await container.resolve(Counter)
        c2 = await container.resolve(Counter)

        c1.value = 42
        assert c2.value == 0  # Different instance


class TestContainerLifecycle:
    """Tests for container lifecycle (freeze, override)."""

    @pytest.mark.asyncio
    async def test_freeze_blocks_new_registrations(self) -> None:
        """freeze() blocks new registrations after being called."""
        container = Container()

        class Service1:
            pass

        class Service2:
            pass

        container.singleton(Service1, Service1())
        container.freeze()

        with pytest.raises(ContainerError):
            container.singleton(Service2, Service2())

    @pytest.mark.asyncio
    async def test_testing_mode_allows_override_after_freeze(self) -> None:
        """Container in testing_mode allows override() after freeze()."""
        container = Container(testing_mode=True)

        class Service:
            def __init__(self):
                self.value = "original"

        container.singleton(Service, factory=Service)
        container.freeze()

        # Override should work in testing mode
        mock = Service()
        mock.value = "mocked"
        container.override(Service, mock)

        resolved = await container.resolve(Service)
        assert resolved.value == "mocked"

    @pytest.mark.asyncio
    async def test_override_replaces_singleton_instance(self) -> None:
        """override() replaces a singleton with a mock instance."""
        container = Container(testing_mode=True)

        class AuthService:
            def __init__(self):
                self.user = "real"

        container.singleton(AuthService, AuthService())
        container.freeze()

        mock = AuthService()
        mock.user = "test"
        container.override(AuthService, mock)

        resolved = await container.resolve(AuthService)
        assert resolved.user == "test"


class TestContainerErrorHandling:
    """Tests for container error handling."""

    @pytest.mark.asyncio
    async def test_resolve_cyclic_dependency_raises(self) -> None:
        """resolve() raises error on cyclic dependencies."""
        container = Container()

        class ServiceA:
            def __init__(self, b: ServiceB):
                self.b = b

        class ServiceB:
            def __init__(self, a: ServiceA):
                self.a = a

        container.transient(ServiceA, ServiceA)
        container.transient(ServiceB, ServiceB)

        with pytest.raises(ContainerError):
            await container.resolve(ServiceA)

    @pytest.mark.asyncio
    async def test_resolve_missing_dependency_raises(self) -> None:
        """resolve() raises error when dependency is not registered."""
        container = Container()

        class MissingDep:
            pass

        class Consumer:
            def __init__(self, dep: MissingDep):
                self.dep = dep

        container.transient(Consumer, Consumer)

        with pytest.raises(ContainerError):
            await container.resolve(Consumer)
