"""Config-alignment tests for LLMProvider."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.config import ClientConfig
from quadkit.ai.llm.di.provider import LLMProvider


class _FakeRegistrar:
    def __init__(self) -> None:
        self.singletons: dict[type, object] = {}

    def singleton(self, cls: type, instance: object) -> None:
        self.singletons[cls] = instance


class TestConfigAlignment:
    def test_provider_declares_config_key_and_model(self) -> None:
        provider = LLMProvider()
        assert provider.config_key == ClientConfig.config_section
        assert provider.config_model is ClientConfig

    @pytest.mark.asyncio
    async def test_injected_config_used_when_no_explicit(self) -> None:
        provider = LLMProvider()
        provider.config = ClientConfig(enabled=False)
        container = _FakeRegistrar()

        await provider.register(container)

        assert container.singletons[ClientConfig] is provider.config

    @pytest.mark.asyncio
    async def test_explicit_config_wins_over_injected(self) -> None:
        explicit = ClientConfig(enabled=True)
        provider = LLMProvider(config=explicit)
        provider.config = ClientConfig(enabled=False)
        container = _FakeRegistrar()

        await provider.register(container)

        assert container.singletons[ClientConfig] is explicit

    @pytest.mark.asyncio
    async def test_default_config_binds_when_nothing_supplied(self) -> None:
        provider = LLMProvider()
        container = _FakeRegistrar()

        await provider.register(container)

        assert isinstance(container.singletons[ClientConfig], ClientConfig)


class TestRoutingProviderConfig:
    def test_routing_provider_is_explicit_only(self) -> None:
        from quadkit.ai.llm.di.routing_provider import LLMRoutingProvider

        provider = LLMRoutingProvider()
        assert provider.config_key is None
        assert provider.config_model is None