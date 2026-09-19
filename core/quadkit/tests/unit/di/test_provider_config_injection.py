"""Tests for QK-012: auto-injection of provider.config before register().

The LifecycleManager must resolve QuadkitConfig from the container and
assign the typed section to provider.config before calling provider.register().
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from quadkit.config import QuadkitConfig
from quadkit.contracts.exceptions.config import ConfigurationError
from quadkit.di.container import Container
from quadkit.di.orchestrator import ProviderOrchestrator
from quadkit.di.provider import Provider
from quadkit.domain import DomainModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass(init=False)
class FakeCacheConfig(DomainModel):
    host: str = "localhost"
    port: int = 6379


class ConfigCapturingProvider(Provider):
    """Provider that records its config at register() time."""

    name = "cache"
    config_key = "cache"
    config_model = FakeCacheConfig

    def __init__(self) -> None:
        super().__init__()
        self.config_at_register: Any = None

    async def register(self, container: Any) -> None:
        self.config_at_register = self.config


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestProviderConfigInjection:
    """Auto-injection of provider.config before register() is called."""

    @pytest.mark.asyncio
    async def test_config_injected_when_key_and_model_declared(self) -> None:
        """Provider with config_key + config_model receives typed config before register()."""
        container = Container()
        qk_config = QuadkitConfig(cache={"host": "redis.local", "port": 6380})
        container.singleton(QuadkitConfig, qk_config)

        provider = ConfigCapturingProvider()
        orchestrator = ProviderOrchestrator(container)
        orchestrator.add(provider)

        await orchestrator.register_all(container)

        assert isinstance(provider.config_at_register, FakeCacheConfig)
        assert provider.config_at_register.host == "redis.local"
        assert provider.config_at_register.port == 6380

    @pytest.mark.asyncio
    async def test_config_key_without_model_raises_at_registration(self) -> None:
        """Declaring config_key without config_model raises ConfigurationError."""

        class BadProvider(Provider):
            name = "bad"
            config_key = "some_section"
            # config_model intentionally omitted

        container = Container()
        container.singleton(QuadkitConfig, QuadkitConfig())

        orchestrator = ProviderOrchestrator(container)
        orchestrator.add(BadProvider())

        with pytest.raises(ConfigurationError, match="config_key='some_section'.*config_model"):
            await orchestrator.register_all(container)

    @pytest.mark.asyncio
    async def test_config_key_without_lex_config_in_container_raises(self) -> None:
        """Declaring config_key when QuadkitConfig is not registered raises ConfigurationError."""

        class OrphanProvider(Provider):
            name = "orphan"
            config_key = "billing"
            config_model = FakeCacheConfig

        container = Container()
        # QuadkitConfig intentionally NOT registered

        orchestrator = ProviderOrchestrator(container)
        orchestrator.add(OrphanProvider())

        with pytest.raises(ConfigurationError, match="QuadkitConfig is not registered"):
            await orchestrator.register_all(container)

    @pytest.mark.asyncio
    async def test_no_config_key_leaves_config_unchanged(self) -> None:
        """Provider without config_key keeps its initial config value unchanged."""

        class PlainProvider(Provider):
            name = "plain"

            def __init__(self) -> None:
                super().__init__()
                self._config = "initial_value"

            async def register(self, container: Any) -> None:
                pass

        container = Container()
        provider = PlainProvider()
        orchestrator = ProviderOrchestrator(container)
        orchestrator.add(provider)

        await orchestrator.register_all(container)

        assert provider.config == "initial_value"

    @pytest.mark.asyncio
    async def test_config_injected_before_register_not_after(self) -> None:
        """provider.config is populated before register() is called, not after."""

        @dataclass(init=False)
        class SomeConfig(DomainModel):
            value: str = "default"

        class OrderTrackingProvider(Provider):
            name = "order_tracking"
            config_key = "svc"
            config_model = SomeConfig

            async def register(self, container: Any) -> None:
                # Record whether config was already injected when register() ran
                self._register_saw_config = isinstance(self.config, SomeConfig)

        container = Container()
        qk_config = QuadkitConfig(svc={"value": "injected"})
        container.singleton(QuadkitConfig, qk_config)

        provider = OrderTrackingProvider()
        orchestrator = ProviderOrchestrator(container)
        orchestrator.add(provider)

        await orchestrator.register_all(container)

        assert provider._register_saw_config is True
        assert provider.config.value == "injected"

    @pytest.mark.asyncio
    async def test_provider_class_attributes_default_to_none(self) -> None:
        """config_key and config_model default to None on the base Provider class."""

        class MinimalProvider(Provider):
            name = "minimal"

        provider = MinimalProvider()
        assert provider.config_key is None
        assert provider.config_model is None
