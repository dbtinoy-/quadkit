"""Config-alignment tests for MCPProvider."""

from __future__ import annotations

import pytest

from quadkit.ai.mcp.config import MCPConfig
from quadkit.ai.mcp.di.provider import MCPProvider


class _FakeRegistrar:
    def __init__(self) -> None:
        self.singletons: dict[type, object] = {}

    def singleton(self, cls: type, instance: object) -> None:
        self.singletons[cls] = instance


class TestConfigAlignment:
    def test_provider_declares_config_key_and_model(self) -> None:
        provider = MCPProvider()
        assert provider.config_key == MCPConfig.config_section
        assert provider.config_model is MCPConfig

    @pytest.mark.asyncio
    async def test_injected_config_used_when_no_explicit(self) -> None:
        provider = MCPProvider()
        provider.config = MCPConfig(enabled=False)
        container = _FakeRegistrar()

        await provider.register(container)

        assert container.singletons[MCPConfig] is provider.config

    @pytest.mark.asyncio
    async def test_explicit_config_wins_over_injected(self) -> None:
        explicit = MCPConfig(enabled=True)
        provider = MCPProvider(config=explicit)
        provider.config = MCPConfig(enabled=False)
        container = _FakeRegistrar()

        await provider.register(container)

        assert container.singletons[MCPConfig] is explicit

    @pytest.mark.asyncio
    async def test_default_config_binds_when_nothing_supplied(self) -> None:
        provider = MCPProvider()
        container = _FakeRegistrar()

        await provider.register(container)

        assert isinstance(container.singletons[MCPConfig], MCPConfig)