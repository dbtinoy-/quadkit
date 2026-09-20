"""Config-alignment tests for CLIProvider."""

from __future__ import annotations

import pytest

from quadkit.cli.config import CLIConfig
from quadkit.cli.di.provider import CLIProvider


class _FakeRegistrar:
    def __init__(self) -> None:
        self.singletons: dict[type, object] = {}

    def singleton(
        self, cls: type, instance: object = None, factory: object = None
    ) -> None:
        self.singletons[cls] = factory if factory is not None else instance

    def transient(self, *args: object, **kwargs: object) -> None:
        pass


class TestConfigAlignment:
    def test_provider_declares_config_key_and_model(self) -> None:
        provider = CLIProvider()
        assert provider.config_key == CLIConfig.config_section
        assert provider.config_model is CLIConfig

    @pytest.mark.asyncio
    async def test_injected_config_used_when_no_explicit(self) -> None:
        provider = CLIProvider()
        provider.config = CLIConfig(color=False)
        container = _FakeRegistrar()

        await provider.register(container)

        assert container.singletons[CLIConfig] is provider.config

    @pytest.mark.asyncio
    async def test_explicit_config_wins_over_injected(self) -> None:
        explicit = CLIConfig(color=True)
        provider = CLIProvider(config=explicit)
        provider.config = CLIConfig(color=False)
        container = _FakeRegistrar()

        await provider.register(container)

        assert container.singletons[CLIConfig] is explicit

    @pytest.mark.asyncio
    async def test_no_binding_when_nothing_supplied(self) -> None:
        provider = CLIProvider()
        container = _FakeRegistrar()

        await provider.register(container)

        assert CLIConfig not in container.singletons