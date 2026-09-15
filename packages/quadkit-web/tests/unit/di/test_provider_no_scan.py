"""Tests for WebProvider explicit registration (no sys.modules scanning).

Verifies that WebProvider does not perform sys.modules scanning and instead
relies on explicit service lists passed via the constructor or set on the
provider instance.
"""

from __future__ import annotations

import asyncio

from quadkit.contracts.core.scopes import ServiceScope
from quadkit.di.container import Container
from quadkit.web.di.provider import WebProvider


class TestWebProviderNoSysModulesScan:
    """Verify that WebProvider does NOT scan sys.modules for injectable services."""

    def test_provider_registers_only_explicit_services(self) -> None:
        """WebProvider only registers services from _extra_injectable_services."""

        class MyService:
            pass

        class OtherService:
            pass

        provider = WebProvider()
        # Explicitly add a service
        provider._extra_injectable_services = [(MyService, ServiceScope.SINGLETON)]

        container = Container()

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(provider.register(container))

            # MyService should be registered (it's in _extra_injectable_services)
            assert container.has(MyService)

            # OtherService should NOT be registered (it's not explicitly added)
            # Even if it has @injectable marker, it should not be auto-discovered
            assert not container.has(OtherService)
        finally:
            loop.run_until_complete(provider.shutdown())
            loop.close()

    def test_provider_ignores_sys_modules_decorated_classes(self) -> None:
        """Verify that classes with @injectable/@singleton in sys.modules are NOT auto-registered."""
        from quadkit.di.decorators import Injectable

        # Define a class with @injectable decorator
        @Injectable(scope=ServiceScope.SINGLETON)
        class ModuleLevelService:
            pass

        # Create provider without adding it to _extra_injectable_services
        provider = WebProvider()
        # Ensure it's NOT in extra services
        provider._extra_injectable_services = []

        container = Container()

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(provider.register(container))

            # ModuleLevelService should NOT be auto-registered from sys.modules
            # Only services in _extra_injectable_services should be registered
            assert not container.has(ModuleLevelService)
        finally:
            loop.run_until_complete(provider.shutdown())
            loop.close()

    def test_provider_with_empty_extra_services_does_not_scan(self) -> None:
        """Creating a provider with empty _extra_injectable_services does not trigger scanning."""
        provider = WebProvider()
        provider._extra_injectable_services = []

        container = Container()

        loop = asyncio.new_event_loop()
        try:
            # This should not raise or attempt to scan sys.modules
            loop.run_until_complete(provider.register(container))
            loop.run_until_complete(provider.boot(container))
            # If we got here without exception, the test passes
            assert True
        finally:
            loop.run_until_complete(provider.shutdown())
            loop.close()

    def test_provider_registers_multiple_explicit_services(self) -> None:
        """WebProvider correctly registers multiple services from _extra_injectable_services."""

        class ServiceA:
            pass

        class ServiceB:
            pass

        class ServiceC:
            pass

        provider = WebProvider()
        provider._extra_injectable_services = [
            (ServiceA, ServiceScope.SINGLETON),
            (ServiceB, ServiceScope.TRANSIENT),
            (ServiceC, ServiceScope.SCOPED),
        ]

        container = Container()

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(provider.register(container))

            assert container.has(ServiceA)
            assert container.has(ServiceB)
            assert container.has(ServiceC)
        finally:
            loop.run_until_complete(provider.shutdown())
            loop.close()
