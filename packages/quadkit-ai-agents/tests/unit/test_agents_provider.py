"""Unit tests for AgentsProvider."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from unittest.mock import AsyncMock, MagicMock

from quadkit.ai.agents.di.provider import AgentsProvider
from quadkit.ai.agents.tools import tool
from quadkit.ai.agents.tools.registry import ToolRegistryImpl
from quadkit.contracts.ai import ToolRegistryProtocol
from quadkit.contracts.core.provider import ProviderPriority
from quadkit.di.container import Container
from quadkit.di.provider import Provider


class TestAgentsProviderStructure:
    """Test AgentsProvider class structure and attributes."""

    def test_provider_class_exists(self) -> None:
        """Verify AgentsProvider class exists and can be instantiated."""
        prov = AgentsProvider()
        assert prov is not None
        assert isinstance(prov, AgentsProvider)

    def test_provider_name(self) -> None:
        """Verify provider has correct name attribute."""
        prov = AgentsProvider()
        assert prov.name == "ai-agents"

    def test_provider_priority(self) -> None:
        """Verify provider has DOMAIN priority."""
        prov = AgentsProvider()
        assert prov.priority == ProviderPriority.DOMAIN

    def test_provider_is_provider_subclass(self) -> None:
        """Verify AgentsProvider is a proper Provider subclass."""
        assert issubclass(AgentsProvider, Provider)

    def test_provider_has_required_methods(self) -> None:
        """Verify provider has all required lifecycle methods."""
        prov = AgentsProvider()
        assert hasattr(prov, "register")
        assert callable(prov.register)
        assert hasattr(prov, "boot")
        assert callable(prov.boot)
        assert hasattr(prov, "shutdown")
        assert callable(prov.shutdown)


class TestAgentsProviderLifecycle:
    """Test AgentsProvider lifecycle methods."""

    @pytest.mark.asyncio
    async def test_register_method_signature(self) -> None:
        """Verify register() method has correct async signature."""
        prov = AgentsProvider()
        container = MagicMock()
        container.singleton = MagicMock()

        # Should complete without error
        await prov.register(container)

    @pytest.mark.asyncio
    async def test_boot_method_signature(self) -> None:
        """Verify boot() method has correct async signature."""
        prov = AgentsProvider()
        container = MagicMock()
        container.resolve = AsyncMock()
        container.resolve_optional = AsyncMock()

        # Should complete without error
        await prov.boot(container)

    @pytest.mark.asyncio
    async def test_strategy_entrypoint_logs_omit_names_and_exception_text(
        self, monkeypatch
    ) -> None:
        """Optional plugin logs expose only event and exception type."""
        import importlib.metadata

        import quadkit.ai.agents.di.provider as provider_module

        private_names = (
            "private_strategy_tenant_42",
            "private_strategy_tenant_43",
        )
        private_error = "token=secret at /srv/private/tenant-42"
        failing_entrypoint = MagicMock()
        failing_entrypoint.name = private_names[0]
        failing_entrypoint.load.side_effect = RuntimeError(private_error)
        skipped_entrypoint = MagicMock()
        skipped_entrypoint.name = private_names[1]
        skipped_entrypoint.load.return_value = object()

        logger = MagicMock()
        monkeypatch.setattr(provider_module, "logger", logger)
        monkeypatch.setattr(
            importlib.metadata,
            "entry_points",
            lambda **kwargs: [failing_entrypoint, skipped_entrypoint],
        )

        await AgentsProvider()._discover_strategies(MagicMock())

        captured = repr(logger.mock_calls)
        assert "agent_strategy_ep_load_failed" in captured
        assert "agent_strategy_ep_skipped" in captured
        assert "RuntimeError" in captured
        assert private_error not in captured
        assert "/srv/private/tenant-42" not in captured
        for name in private_names:
            assert name not in captured

    @pytest.mark.asyncio
    async def test_shutdown_method_signature(self) -> None:
        """Verify shutdown() method has correct async signature."""
        prov = AgentsProvider()

        # Should complete without error
        await prov.shutdown()

class TestAgentsProviderDITokens:
    """Regression tests for DI token aliasing in AgentsProvider."""

    @pytest.mark.asyncio
    async def test_tool_registry_protocol_and_impl_resolve_same_singleton(self) -> None:
        """ToolRegistryProtocol and ToolRegistryImpl resolve to one shared instance."""
        prov = AgentsProvider()
        container = Container()

        await prov.register(container)

        registry_impl = await container.resolve(ToolRegistryImpl)
        registry_protocol = await container.resolve(ToolRegistryProtocol)

        assert registry_impl is registry_protocol

        @tool
        async def ping() -> str:
            """Ping test tool."""
            return "pong"

        registry_impl.register(ping)

        assert registry_protocol.get("ping") is ping
        assert any(item.name == "ping" for item in registry_protocol.list_tools())


class TestAgentsProviderGuardWiring:
    """Guard pipeline wiring across the DI boundary (D2)."""

    class _ResolveAll:
        """Fake resolver: returns stubs; GuardPipelineProtocol resolves to a sentinel."""

        def __init__(self, sentinel: object = None) -> None:
            self._sentinel = sentinel

        async def resolve_optional(self, token: object) -> object:
            from quadkit.contracts.ai.guards import GuardPipelineProtocol

            if token is GuardPipelineProtocol:
                return self._sentinel
            return None

        def bind(self, token: object, impl: object) -> None:  # noqa: ARG002
            self.bound = (token, impl)

        async def resolve(self, token: object) -> object:
            return SimpleNamespace()

    @pytest.mark.asyncio
    async def test_boot_injects_guard_pipeline_into_executor(self) -> None:
        from quadkit.ai.agents.di.provider import AgentsProvider

        sentinel = SimpleNamespace(is_guard_pipeline=True)
        provider = AgentsProvider()
        resolver = self._ResolveAll(sentinel)
        await provider.boot(resolver)  # type: ignore[arg-type]

        _, executor = resolver.bound
        assert executor._guard_pipeline is sentinel

    @pytest.mark.asyncio
    async def test_boot_without_guard_module_sets_none(self) -> None:
        from quadkit.ai.agents.di.provider import AgentsProvider

        provider = AgentsProvider()
        resolver = self._ResolveAll(None)
        await provider.boot(resolver)  # type: ignore[arg-type]

        _, executor = resolver.bound
        assert executor._guard_pipeline is None

