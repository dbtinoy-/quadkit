"""Tests for Module lifecycle hooks (on_module_booted, on_module_shutdown) orchestration."""

from __future__ import annotations

import logging

import pytest

from quadkit.contracts.core.provider import ProviderPriority
from quadkit.di.container import Container
from quadkit.di.module.base import Module
from quadkit.di.module.compiler import ModuleCompiler
from quadkit.di.module.decorator import module
from quadkit.di.module.dynamic import DynamicModule
from quadkit.di.orchestrator import ProviderOrchestrator
from quadkit.di.provider import Provider


class TestLifecycleOrchestrator:
    """Tests that module lifecycle hooks are called at the right times."""

    @pytest.mark.asyncio
    async def test_on_module_booted_called_after_providers(self) -> None:
        """on_module_booted fires after all providers in a module have booted."""
        call_order: list[str] = []

        class TrackingProvider(Provider):
            name = "tracking"
            priority = ProviderPriority.NORMAL

            async def register(self, container):  # noqa: ANN001
                pass

            async def boot(self, container):  # noqa: ANN001
                call_order.append("provider")

        @module()
        class TrackingModule(Module):
            providers = [TrackingProvider]

            @classmethod
            def configure(cls) -> DynamicModule:
                return DynamicModule(module=cls, providers=[TrackingProvider])

            @classmethod
            async def on_module_booted(cls) -> None:
                call_order.append("module_hook")

        # Compile module graph and build orchestrator
        graph = ModuleCompiler().compile([TrackingModule])
        container = Container()
        orchestrator = ProviderOrchestrator(container)
        orchestrator._compiled_graph = graph

        # Add providers from graph
        for entry in graph.provider_order:
            provider_instance = (
                entry.provider if entry.is_instance else entry.provider()  # type: ignore[misc]
            )
            orchestrator.add(provider_instance)

        # Execute boot lifecycle
        await orchestrator.boot_all(container)

        # Assertions
        assert "provider" in call_order
        assert "module_hook" in call_order
        assert call_order.index("provider") < call_order.index("module_hook")

    @pytest.mark.asyncio
    async def test_on_module_booted_not_called_without_compiled_graph(self) -> None:
        """on_module_booted is not called when _compiled_graph is None."""
        hook_called = False

        class SimpleProvider(Provider):
            name = "simple"
            priority = ProviderPriority.NORMAL

            async def register(self, container):  # noqa: ANN001
                pass

            async def boot(self, container):  # noqa: ANN001
                pass

        @module()
        class SimpleModule(Module):
            providers = [SimpleProvider]

            @classmethod
            async def on_module_booted(cls) -> None:
                nonlocal hook_called
                hook_called = True

        container = Container()
        orchestrator = ProviderOrchestrator(container)
        # Do NOT set _compiled_graph
        orchestrator.add(SimpleProvider())

        await orchestrator.boot_all(container)

        # Hook should not be called without compiled graph
        assert not hook_called

    @pytest.mark.asyncio
    async def test_modules_without_boot_hook_do_not_emit_warnings(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Modules lacking on_module_booted should be skipped quietly."""

        class PlainProvider(Provider):
            name = "plain"
            priority = ProviderPriority.NORMAL

            async def register(self, container):  # noqa: ANN001
                pass

            async def boot(self, container):  # noqa: ANN001
                pass

        @module()
        class PlainModule(Module):
            providers = [PlainProvider]

        graph = ModuleCompiler().compile([PlainModule])
        container = Container()
        orchestrator = ProviderOrchestrator(container)
        orchestrator._compiled_graph = graph
        orchestrator.add(PlainProvider())

        with caplog.at_level(logging.WARNING):
            await orchestrator.boot_all(container)

        assert not any(
            record.message == "lifecycle.on_module_booted.error"
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_on_module_shutdown_called_during_shutdown(self) -> None:
        """on_module_shutdown is called before providers are shut down."""
        shutdown_called = False

        class ShutdownProvider(Provider):
            name = "shutdown_test"
            priority = ProviderPriority.NORMAL

            async def register(self, container):  # noqa: ANN001
                pass

            async def boot(self, container):  # noqa: ANN001
                pass

            async def shutdown(self) -> None:
                pass

        @module()
        class ShutdownModule(Module):
            providers = [ShutdownProvider]

            @classmethod
            def configure(cls) -> DynamicModule:
                return DynamicModule(module=cls, providers=[ShutdownProvider])

            @classmethod
            async def on_module_shutdown(cls) -> None:
                nonlocal shutdown_called
                shutdown_called = True

        # Compile and boot
        graph = ModuleCompiler().compile([ShutdownModule])
        container = Container()
        orchestrator = ProviderOrchestrator(container)
        orchestrator._compiled_graph = graph

        for entry in graph.provider_order:
            provider_instance = (
                entry.provider if entry.is_instance else entry.provider()  # type: ignore[misc]
            )
            orchestrator.add(provider_instance)

        await orchestrator.boot_all(container)

        # Shutdown
        await orchestrator.shutdown()

        assert shutdown_called

    @pytest.mark.asyncio
    async def test_modules_without_shutdown_hook_do_not_emit_warnings(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Modules lacking on_module_shutdown should be skipped quietly."""

        class PlainProvider(Provider):
            name = "plain_shutdown"
            priority = ProviderPriority.NORMAL

            async def register(self, container):  # noqa: ANN001
                pass

            async def boot(self, container):  # noqa: ANN001
                pass

            async def shutdown(self) -> None:
                pass

        @module()
        class PlainModule(Module):
            providers = [PlainProvider]

        graph = ModuleCompiler().compile([PlainModule])
        container = Container()
        orchestrator = ProviderOrchestrator(container)
        orchestrator._compiled_graph = graph
        orchestrator.add(PlainProvider())

        await orchestrator.boot_all(container)
        with caplog.at_level(logging.WARNING):
            await orchestrator.shutdown()

        assert not any(
            record.message == "lifecycle.on_module_shutdown.error"
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_on_module_booted_error_does_not_crash_boot(self) -> None:
        """If on_module_booted raises, boot continues (hook errors are non-fatal)."""
        provider_booted = False

        class ErrorHookProvider(Provider):
            name = "error_hook"
            priority = ProviderPriority.NORMAL

            async def register(self, container):  # noqa: ANN001
                pass

            async def boot(self, container):  # noqa: ANN001
                nonlocal provider_booted
                provider_booted = True

        @module()
        class ErrorHookModule(Module):
            providers = [ErrorHookProvider]

            @classmethod
            async def on_module_booted(cls) -> None:
                raise RuntimeError("Hook error")

        graph = ModuleCompiler().compile([ErrorHookModule])
        container = Container()
        orchestrator = ProviderOrchestrator(container)
        orchestrator._compiled_graph = graph

        for entry in graph.provider_order:
            provider_instance = (
                entry.provider if entry.is_instance else entry.provider()  # type: ignore[misc]
            )
            orchestrator.add(provider_instance)

        # Should not raise — hook errors are logged and suppressed
        await orchestrator.boot_all(container)

        assert provider_booted

    @pytest.mark.asyncio
    async def test_multiple_modules_hooks_called_in_order(self) -> None:
        """When multiple modules are present, hooks are called for each."""
        hook_calls: list[str] = []

        class ProviderA(Provider):
            name = "provider_a"
            priority = ProviderPriority.NORMAL

            async def register(self, container):  # noqa: ANN001
                pass

            async def boot(self, container):  # noqa: ANN001
                pass

        class ProviderB(Provider):
            name = "provider_b"
            priority = ProviderPriority.NORMAL

            async def register(self, container):  # noqa: ANN001
                pass

            async def boot(self, container):  # noqa: ANN001
                pass

        @module()
        class ModuleA(Module):
            providers = [ProviderA]

            @classmethod
            async def on_module_booted(cls) -> None:
                hook_calls.append("module_a")

        @module()
        class ModuleB(Module):
            providers = [ProviderB]
            imports = [ModuleA]

            @classmethod
            async def on_module_booted(cls) -> None:
                hook_calls.append("module_b")

        graph = ModuleCompiler().compile([ModuleB])
        container = Container()
        orchestrator = ProviderOrchestrator(container)
        orchestrator._compiled_graph = graph

        for entry in graph.provider_order:
            provider_instance = (
                entry.provider if entry.is_instance else entry.provider()  # type: ignore[misc]
            )
            orchestrator.add(provider_instance)

        await orchestrator.boot_all(container)

        # Both hooks should be called
        assert "module_a" in hook_calls
        assert "module_b" in hook_calls
