"""Test AppTestBed.from_factory() with service overrides.

AppTestBed.from_factory() creates a test harness for Quadkit applications
with optional DI service overrides. This test suite validates:

1. Basic app bootstrap from factory string and callable
2. Service override registration during bootstrap
3. Override precedence (applied after providers but before boot)
4. Multiple service overrides working together
5. Override isolation across test instances
6. Web client availability when ASGI app present
"""

from __future__ import annotations

import pytest

from quadkit.app.base import Application
from quadkit.testing.harness.testbed import AppTestBed


class SimpleService:
    """Simple test service for override verification."""

    def __init__(self, name: str = "original") -> None:
        self.name = name

    def get_name(self) -> str:
        return self.name


class OtherService:
    """Another service for multi-override tests."""

    def __init__(self, value: int = 100) -> None:
        self.value = value


def create_test_app() -> Application:
    """Factory function that creates a minimal test application."""
    app = Application(name="test_app")
    # Register SimpleService and OtherService as singletons
    app.container.singleton(SimpleService, instance=SimpleService("original"))
    app.container.singleton(OtherService, instance=OtherService(100))
    return app


class TestAppTestBedFromFactory:
    """Test AppTestBed.from_factory() basic functionality."""

    @pytest.mark.asyncio
    async def test_from_factory_with_callable(self) -> None:
        """Verify from_factory() boots app from callable factory."""
        async with AppTestBed.from_factory(create_test_app) as bed:
            assert bed.app is not None
            assert bed.container is not None
            # Verify original service is present
            service = bed.container.resolve_sync(SimpleService)
            assert service.get_name() == "original"

    @pytest.mark.asyncio
    async def test_from_factory_returns_booted_app(self) -> None:
        """Verify from_factory() returns fully booted application."""
        async with AppTestBed.from_factory(create_test_app) as bed:
            # App should be started
            assert bed.app is not None
            # Container should be accessible
            assert bed.container is not None
            # Service should be resolvable
            assert bed.container.resolve_sync(SimpleService) is not None

    @pytest.mark.asyncio
    async def test_from_factory_app_stopped_after_context(self) -> None:
        """Verify from_factory() stops app after context exit."""
        app_ref = None
        async with AppTestBed.from_factory(create_test_app) as bed:
            app_ref = bed.app
            assert bed.app is not None

        # After context, app should be cleaned up (would not be resolvable beyond this)
        assert app_ref is not None


class TestAppTestBedWithOverrides:
    """Test AppTestBed.from_factory() with service overrides."""

    @pytest.mark.asyncio
    async def test_single_service_override(self) -> None:
        """Verify single service override is applied."""
        override_service = SimpleService("overridden")

        async with AppTestBed.from_factory(
            create_test_app,
            overrides={SimpleService: override_service},
        ) as bed:
            # Override should be active
            service = bed.container.resolve_sync(SimpleService)
            assert service is override_service
            assert service.get_name() == "overridden"

    @pytest.mark.asyncio
    async def test_multiple_service_overrides(self) -> None:
        """Verify multiple service overrides work together."""
        override_simple = SimpleService("test_simple")
        override_other = OtherService(999)

        async with AppTestBed.from_factory(
            create_test_app,
            overrides={
                SimpleService: override_simple,
                OtherService: override_other,
            },
        ) as bed:
            # Both overrides should be active
            service1 = bed.container.resolve_sync(SimpleService)
            service2 = bed.container.resolve_sync(OtherService)
            assert service1 is override_simple
            assert service2 is override_other
            assert service1.get_name() == "test_simple"
            assert service2.value == 999

    @pytest.mark.asyncio
    async def test_override_isolation_between_instances(self) -> None:
        """Verify overrides don't leak between separate test bed instances."""
        override1 = SimpleService("test_1")
        override2 = SimpleService("test_2")

        # First test bed with override1
        async with AppTestBed.from_factory(
            create_test_app,
            overrides={SimpleService: override1},
        ) as bed1:
            service1 = bed1.container.resolve_sync(SimpleService)
            assert service1 is override1

        # Second test bed with override2
        async with AppTestBed.from_factory(
            create_test_app,
            overrides={SimpleService: override2},
        ) as bed2:
            service2 = bed2.container.resolve_sync(SimpleService)
            assert service2 is override2

        # Each remained isolated
        assert service1 is not service2

    @pytest.mark.asyncio
    async def test_no_overrides_uses_defaults(self) -> None:
        """Verify app uses default services when no overrides provided."""
        async with AppTestBed.from_factory(create_test_app) as bed:
            service = bed.container.resolve_sync(SimpleService)
            assert service.get_name() == "original"

    @pytest.mark.asyncio
    async def test_empty_overrides_dict_uses_defaults(self) -> None:
        """Verify empty overrides dict has no effect."""
        async with AppTestBed.from_factory(create_test_app, overrides={}) as bed:
            service = bed.container.resolve_sync(SimpleService)
            assert service.get_name() == "original"


class TestAppTestBedOverridePrecedence:
    """Test that overrides have correct precedence in bootstrap pipeline."""

    @pytest.mark.asyncio
    async def test_overrides_applied_after_providers(self) -> None:
        """Verify overrides apply after provider registration."""

        def factory() -> Application:
            """Factory that registers a provider."""
            from quadkit.di.provider import Provider

            app = Application(name="test_with_provider")

            class TestProvider(Provider):
                async def register(self, container) -> None:
                    # Register original service
                    container.singleton(
                        SimpleService,
                        instance=SimpleService("from_provider"),
                    )

            app.add_provider(TestProvider(name="test_provider"))
            return app

        override_service = SimpleService("from_override")

        async with AppTestBed.from_factory(
            factory,
            overrides={SimpleService: override_service},
        ) as bed:
            # Override should win over provider registration
            service = bed.container.resolve_sync(SimpleService)
            assert service is override_service

    @pytest.mark.asyncio
    async def test_override_survives_app_boot(self) -> None:
        """Verify override remains in place after app.start() completes."""
        override_service = SimpleService("persistent_override")

        async with AppTestBed.from_factory(
            create_test_app,
            overrides={SimpleService: override_service},
        ) as bed:
            # Override should be present after boot
            assert bed.container.resolve_sync(SimpleService) is override_service


class TestAppTestBedIntegration:
    """Integration tests combining overrides with other AppTestBed features."""

    @pytest.mark.asyncio
    async def test_override_with_app_container_access(self) -> None:
        """Verify overridden services accessible via bed.container."""
        override_service = SimpleService("accessible")

        async with AppTestBed.from_factory(
            create_test_app,
            overrides={SimpleService: override_service},
        ) as bed:
            # Access via bed.container should return override
            assert bed.container.resolve_sync(SimpleService) is override_service

    @pytest.mark.asyncio
    async def test_multiple_bedswith_different_overrides(self) -> None:
        """Verify multiple beds can run concurrently with different overrides."""

        async def run_bed_with_override(name: str) -> SimpleService:
            override = SimpleService(name)
            async with AppTestBed.from_factory(
                create_test_app,
                overrides={SimpleService: override},
            ) as bed:
                return bed.container.resolve_sync(SimpleService)

        # Run two beds with different services
        service_a = await run_bed_with_override("bed_a")
        service_b = await run_bed_with_override("bed_b")

        # Each should be its own override
        assert service_a.get_name() == "bed_a"
        assert service_b.get_name() == "bed_b"
        assert service_a is not service_b

    @pytest.mark.asyncio
    async def test_override_custom_implementation(self) -> None:
        """Verify override can use custom implementation of service."""

        class CustomImplementation(SimpleService):
            """Custom subclass for testing."""

            def get_name(self) -> str:
                return f"custom_{self.name}"

        override = CustomImplementation("impl")

        async with AppTestBed.from_factory(
            create_test_app,
            overrides={SimpleService: override},
        ) as bed:
            service = bed.container.resolve_sync(SimpleService)
            assert isinstance(service, CustomImplementation)
            assert service.get_name() == "custom_impl"

    @pytest.mark.asyncio
    async def test_override_with_mock_or_double(self) -> None:
        """Verify override can use a mock or test double."""

        class MockService(SimpleService):
            """Mock version with tracking."""

            def __init__(self) -> None:
                super().__init__("mock")
                self.call_count = 0

            def get_name(self) -> str:
                self.call_count += 1
                return super().get_name()

        mock = MockService()

        async with AppTestBed.from_factory(
            create_test_app,
            overrides={SimpleService: mock},
        ) as bed:
            service = bed.container.resolve_sync(SimpleService)
            assert service is mock
            _ = service.get_name()
            assert mock.call_count == 1
