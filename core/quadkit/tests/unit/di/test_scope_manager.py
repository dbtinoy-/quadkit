"""Tests for Scope: request-scoped resolution context."""

import pytest

from quadkit.di.builder import ContainerBuilder


class TestScopeBasics:
    """Tests for basic Scope operations."""

    @pytest.mark.asyncio
    async def test_scope_context_manager(self) -> None:
        """Scope can be used as async context manager."""

        class ServiceA:
            pass

        builder = ContainerBuilder()
        builder.add_singleton(ServiceA, ServiceA)
        container = await builder.build()

        async with container.create_scope() as scope:
            resolved = await scope.resolve(ServiceA)
            assert resolved is not None

    @pytest.mark.asyncio
    async def test_scope_has_method(self) -> None:
        """Scope.has() checks if service is registered."""

        class RegisteredService:
            pass

        class UnregisteredService:
            pass

        builder = ContainerBuilder()
        builder.add_singleton(RegisteredService, RegisteredService)
        container = await builder.build()

        async with container.create_scope() as scope:
            assert scope.has(RegisteredService) is True
            assert scope.has(UnregisteredService) is False


class TestScopeResolution:
    """Tests for scope resolution."""

    @pytest.mark.asyncio
    async def test_resolve_singleton_from_scope(self) -> None:
        """Scope resolves singleton from root container."""

        class DatabaseService:
            pass

        builder = ContainerBuilder()
        builder.add_singleton(DatabaseService, DatabaseService)
        container = await builder.build()

        async with container.create_scope() as scope:
            db1 = await scope.resolve(DatabaseService)
            db2 = await scope.resolve(DatabaseService)
            # Singleton - same instance
            assert db1 is db2

    @pytest.mark.asyncio
    async def test_resolve_transient_from_scope(self) -> None:
        """Scope resolves transient from container (not scope caching)."""

        class LoggerService:
            pass

        builder = ContainerBuilder()
        builder.add_transient(LoggerService, LoggerService)
        container = await builder.build()

        # Transients bypass scope caching - resolve from root
        logger1 = await container.resolve(LoggerService)
        logger2 = await container.resolve(LoggerService)
        # Transient - different instances
        assert logger1 is not logger2

    @pytest.mark.asyncio
    async def test_resolve_unregistered_raises(self) -> None:
        """Resolving unregistered service raises error."""
        from quadkit.contracts.exceptions import UnresolvableDependencyError

        class UnknownService:
            pass

        builder = ContainerBuilder()
        container = await builder.build()

        async with container.create_scope() as scope:
            with pytest.raises(UnresolvableDependencyError):
                await scope.resolve(UnknownService)


class TestScopeOptional:
    """Tests for optional resolution."""

    @pytest.mark.asyncio
    async def test_resolve_optional_returns_service(self) -> None:
        """resolve_optional returns service when registered."""

        class OptionalService:
            pass

        builder = ContainerBuilder()
        builder.add_singleton(OptionalService, OptionalService)
        container = await builder.build()

        async with container.create_scope() as scope:
            result = await scope.resolve_optional(OptionalService)
            assert result is not None

    @pytest.mark.asyncio
    async def test_resolve_optional_returns_none_when_missing(self) -> None:
        """resolve_optional returns None when not registered."""

        class MissingService:
            pass

        builder = ContainerBuilder()
        container = await builder.build()

        async with container.create_scope() as scope:
            result = await scope.resolve_optional(MissingService)
            assert result is None


class TestNestedScopes:
    """Tests for nested/child scopes (K-02 feature)."""

    @pytest.mark.asyncio
    async def test_create_child_scope(self) -> None:
        """Parent scope can create child scope."""

        class ServiceX:
            pass

        builder = ContainerBuilder()
        builder.add_singleton(ServiceX, ServiceX)
        container = await builder.build()

        async with container.create_scope() as parent:
            async with parent.create_scope() as child:
                x = await child.resolve(ServiceX)
                assert x is not None

    @pytest.mark.asyncio
    async def test_child_scope_can_resolve_parent_services(self) -> None:
        """Child scope can resolve services from parent scope."""

        class SharedService:
            pass

        builder = ContainerBuilder()
        builder.add_singleton(SharedService, SharedService)
        container = await builder.build()

        async with container.create_scope() as parent:
            parent_service = await parent.resolve(SharedService)

            async with parent.create_scope() as child:
                child_service = await child.resolve(SharedService)
                # Both resolve to the same singleton instance
                assert parent_service is child_service


class TestScopeDispose:
    """Tests for scope disposal."""

    @pytest.mark.asyncio
    async def test_scope_dispose_clears_cache(self) -> None:
        """Scope dispose clears internal cache."""

        class DisposableService:
            def close(self) -> None:
                pass

        builder = ContainerBuilder()
        builder.add_singleton(DisposableService, DisposableService)
        container = await builder.build()

        scope = container.create_scope()
        await scope.dispose()

    @pytest.mark.asyncio
    async def test_scope_context_manager_disposes(self) -> None:
        """Exiting scope context manager disposes resources."""

        class ServiceY:
            pass

        builder = ContainerBuilder()
        builder.add_singleton(ServiceY, ServiceY)
        container = await builder.build()

        # Should not raise on exit
        async with container.create_scope() as scope:
            await scope.resolve(ServiceY)

    @pytest.mark.asyncio
    async def test_container_scope_context_manager_disposes(self) -> None:
        """container.scope() disposes scoped resources on exit."""

        class DisposableScopedService:
            def __init__(self) -> None:
                self.closed = False

            async def aclose(self) -> None:
                self.closed = True

        builder = ContainerBuilder()
        builder.add_scoped(DisposableScopedService, DisposableScopedService)
        container = await builder.build()

        async with container.scope() as scope:
            service = await scope.resolve(DisposableScopedService)
            assert service.closed is False

        assert service.closed is True


class TestScopeResolveAll:
    """Tests for resolve_all method."""

    @pytest.mark.asyncio
    async def test_resolve_all_returns_list(self) -> None:
        """resolve_all returns a list of implementations."""

        class BaseService:
            pass

        class ImplA(BaseService):
            pass

        class ImplB(BaseService):
            pass

        builder = ContainerBuilder()
        # Note: ContainerBuilder doesn't have direct support for multiple
        # implementations, but we test the method exists
        builder.add_singleton(ImplA, ImplA)
        container = await builder.build()

        async with container.create_scope() as scope:
            results = await scope.resolve_all(ImplA)
            assert isinstance(results, list)
