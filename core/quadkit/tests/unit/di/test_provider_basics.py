"""Tests for Provider pattern: register, boot, shutdown, and lifecycle."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.core.provider import ProviderPriority
from quadkit.di.provider import Provider


class TestProviderConstruction:
    """Tests for Provider construction and attributes."""

    def test_provider_has_name_attribute(self) -> None:
        """Providers must define a name attribute."""

        class MyProvider(Provider):
            name = "my_provider"

        provider = MyProvider()
        assert provider.name == "my_provider"

    def test_provider_has_default_priority(self) -> None:
        """Providers have default priority of NORMAL."""
        from quadkit.contracts.core.provider import ProviderPriority

        class MyProvider(Provider):
            name = "test"

        provider = MyProvider()
        assert provider.priority == ProviderPriority.NORMAL

    def test_provider_can_override_priority(self) -> None:
        """Providers can override priority."""

        class HighPriorityProvider(Provider):
            name = "high"
            priority = ProviderPriority.CRITICAL

        provider = HighPriorityProvider()
        assert provider.priority == ProviderPriority.CRITICAL


class TestProviderLifecycle:
    """Tests for Provider lifecycle methods."""

    @pytest.mark.asyncio
    async def test_register_method_exists(self) -> None:
        """Providers must implement register method."""

        class TestProvider(Provider):
            name = "test"

            async def register(self, container: Any) -> None:
                pass

        provider = TestProvider()
        assert hasattr(provider, "register")

    @pytest.mark.asyncio
    async def test_boot_method_exists(self) -> None:
        """Providers may implement boot method."""

        class TestProvider(Provider):
            name = "test"

            async def boot(self, container: Any) -> None:
                pass

        provider = TestProvider()
        assert hasattr(provider, "boot")

    @pytest.mark.asyncio
    async def test_shutdown_method_exists(self) -> None:
        """Providers may implement shutdown method."""

        class TestProvider(Provider):
            name = "test"

            async def shutdown(self) -> None:
                pass

        provider = TestProvider()
        assert hasattr(provider, "shutdown")

    @pytest.mark.asyncio
    async def test_register_called_during_bootstrap(self) -> None:
        """register() is called when provider is added to app."""

        class TrackingProvider(Provider):
            name = "tracking"
            register_called = False

            @classmethod
            async def register(cls, container: Any) -> None:
                cls.register_called = True

        # Reset class state
        TrackingProvider.register_called = False

        provider = TrackingProvider()
        await provider.register(None)

        assert TrackingProvider.register_called is True


class TestProviderStateTransitions:
    """Tests for Provider state transitions."""

    @pytest.mark.asyncio
    async def test_provider_initial_state_created(self) -> None:
        """Provider starts in CREATED state."""
        from quadkit.di.provider import ProviderState

        class TestProvider(Provider):
            name = "test"

        provider = TestProvider()
        assert provider.state == ProviderState.CREATED


class TestProviderPriorityOrdering:
    """Tests for Provider priority ordering."""

    def test_priority_ordering_critical_lowest(self) -> None:
        """CRITICAL priority is lowest (boots first)."""
        assert ProviderPriority.CRITICAL < ProviderPriority.INFRASTRUCTURE
        assert ProviderPriority.CRITICAL < ProviderPriority.NORMAL

    def test_priority_ordering_infrastructure_before_normal(self) -> None:
        """INFRASTRUCTURE comes before NORMAL."""
        assert ProviderPriority.INFRASTRUCTURE < ProviderPriority.NORMAL

    def test_priority_ordering_domain_after_normal(self) -> None:
        """DOMAIN comes after NORMAL."""
        assert ProviderPriority.NORMAL < ProviderPriority.DOMAIN

    def test_priority_ordering_presentation_last(self) -> None:
        """PRESENTATION has high value (boots late)."""
        assert ProviderPriority.DOMAIN < ProviderPriority.PRESENTATION
        assert ProviderPriority.PRESENTATION < ProviderPriority.COMMS

    def test_priority_ordering_low_is_highest(self) -> None:
        """LOW has highest value (boots last)."""
        assert ProviderPriority.COMMS < ProviderPriority.LOW


class TestProviderConfig:
    """Tests for Provider configuration injection."""

    def test_provider_has_config_attribute(self) -> None:
        """Providers have config attribute after injection."""

        class TestProvider(Provider):
            name = "test"
            config_key = "my_config"

        provider = TestProvider()
        # Initially None
        assert provider.config is None

    def test_provider_without_config_key_is_none(self) -> None:
        """Providers without config_key have None config."""

        class TestProvider(Provider):
            name = "test"

        provider = TestProvider()
        assert provider.config is None

    def test_provider_can_define_config_model(self) -> None:
        """Providers can define config_model for type safety."""

        from dataclasses import dataclass

        @dataclass
        class DatabaseConfig:
            host: str = "localhost"
            port: int = 5432

        class TestProvider(Provider):
            name = "test"
            config_key = "db"
            config_model = DatabaseConfig

        provider = TestProvider()
        assert provider.config_model == DatabaseConfig


class TestProviderBootErrors:
    """Tests for Provider boot error handling."""

    @pytest.mark.asyncio
    async def test_boot_can_raise_exception(self) -> None:
        """Boot can raise exception on failure."""

        class FailingProvider(Provider):
            name = "failing"

            async def boot(self, container: Any) -> None:
                raise RuntimeError("Boot failed")

        provider = FailingProvider()
        with pytest.raises(RuntimeError, match="Boot failed"):
            await provider.boot(None)

    @pytest.mark.asyncio
    async def test_register_can_raise_exception(self) -> None:
        """Register can raise exception on failure."""

        class FailingProvider(Provider):
            name = "failing"

            async def register(self, container: Any) -> None:
                raise ValueError("Registration failed")

        provider = FailingProvider()
        with pytest.raises(ValueError, match="Registration failed"):
            await provider.register(None)


class TestProviderSubclassing:
    """Tests for creating custom Provider subclasses."""

    def test_can_create_simple_provider(self) -> None:
        """Can create a simple Provider subclass."""

        class SimpleProvider(Provider):
            name = "simple"
            priority = ProviderPriority.LOW

        provider = SimpleProvider()
        assert provider.name == "simple"
        assert provider.priority == ProviderPriority.LOW

    def test_can_create_provider_with_custom_config(self) -> None:
        """Can create provider with custom configuration."""

        class ConfiguredProvider(Provider):
            name = "configured"
            config_key = "app.features"

        provider = ConfiguredProvider()
        assert provider.config_key == "app.features"

    def test_provider_inheritance_preserves_base_methods(self) -> None:
        """Inherited providers preserve base Provider methods."""

        class ChildProvider(Provider):
            name = "child"

        provider = ChildProvider()
        # Should have all base methods
        assert hasattr(provider, "register")
        assert hasattr(provider, "boot")
        assert hasattr(provider, "shutdown")
        assert hasattr(provider, "health_check")
