# file: tests/di/module/test_lifecycle.py
"""Tests for module lifecycle hooks — OnModuleInitProtocol, OnApplicationShutdownProtocol."""

from __future__ import annotations

import pytest

from quadkit.contracts.core.di import ContainerRegistrarProtocol, ContainerResolverProtocol
from quadkit.contracts.core.lifecycle import OnModuleInitProtocol, OnApplicationBootstrapProtocol
from quadkit.di.container import Container
from quadkit.di.module import DynamicModule, module
from quadkit.di.orchestrator import ProviderOrchestrator
from quadkit.di.provider import Provider, ProviderPriority


class _TrackingProvider(Provider):
    """Provider that records lifecycle events."""

    name = "tracking"
    calls: list[str] = []

    def __init__(self):
        super().__init__()
        self.__class__.calls = []

    async def register(self, container: ContainerRegistrarProtocol) -> None:
        self.__class__.calls.append(f"{self.name}:register")

    async def boot(self, container: ContainerResolverProtocol) -> None:
        self.__class__.calls.append(f"{self.name}:boot")

    async def shutdown(self) -> None:
        self.__class__.calls.append(f"{self.name}:shutdown")


class _InitTrackingProvider(_TrackingProvider, OnModuleInitProtocol):
    name = "init_tracking"

    async def on_module_init(self) -> None:
        self.__class__.calls.append(f"{self.name}:on_module_init")


class _BootstrapTrackingProvider(_TrackingProvider, OnApplicationBootstrapProtocol):
    name = "bootstrap_tracking"

    async def on_application_bootstrap(self) -> None:
        self.__class__.calls.append(f"{self.name}:on_application_bootstrap")


class TestOnModuleInit:
    """Test that OnModuleInitProtocol fires after boot."""

    @pytest.mark.asyncio
    async def test_on_module_init_called_after_boot(self):
        @module(providers=[_InitTrackingProvider])
        class MyModule:
            pass

        container = Container()
        orchestrator = ProviderOrchestrator(container)
        orchestrator.add_module(MyModule)

        await orchestrator.boot_all(container)

        assert "init_tracking:register" in _InitTrackingProvider.calls
        assert "init_tracking:boot" in _InitTrackingProvider.calls
        assert "init_tracking:on_module_init" in _InitTrackingProvider.calls

        # Order: register → boot → on_module_init
        reg_idx = _InitTrackingProvider.calls.index("init_tracking:register")
        boot_idx = _InitTrackingProvider.calls.index("init_tracking:boot")
        init_idx = _InitTrackingProvider.calls.index("init_tracking:on_module_init")
        assert reg_idx < boot_idx < init_idx

        await orchestrator.shutdown()


class TestOnApplicationBootstrap:
    """Test that OnApplicationBootstrapProtocol fires after ALL providers boot."""

    @pytest.mark.asyncio
    async def test_bootstrap_called_after_all_boot(self):
        @module(providers=[_BootstrapTrackingProvider])
        class MyModule:
            pass

        container = Container()
        orchestrator = ProviderOrchestrator(container)
        orchestrator.add_module(MyModule)

        await orchestrator.boot_all(container)

        assert "bootstrap_tracking:boot" in _BootstrapTrackingProvider.calls
        assert (
            "bootstrap_tracking:on_application_bootstrap"
            in _BootstrapTrackingProvider.calls
        )

        boot_idx = _BootstrapTrackingProvider.calls.index("bootstrap_tracking:boot")
        bootstrap_idx = _BootstrapTrackingProvider.calls.index(
            "bootstrap_tracking:on_application_bootstrap",
        )
        assert boot_idx < bootstrap_idx

        await orchestrator.shutdown()
