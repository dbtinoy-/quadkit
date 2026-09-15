"""Tests for Provider.reset_state (re-arming providers for test restarts)."""

from __future__ import annotations

import pytest

from quadkit.contracts.core.provider import ProviderPriority
from quadkit.di.container import Container
from quadkit.di.orchestrator import ProviderOrchestrator
from quadkit.di.provider import Provider, ProviderState


class _ProbeProvider(Provider):
    name = "reset-probe"
    priority = ProviderPriority.NORMAL


class TestProviderResetState:
    """reset_state() returns a provider to a bootable lifecycle state."""

    def test_fresh_provider_is_created(self) -> None:
        provider = _ProbeProvider()
        assert provider.state == ProviderState.CREATED
        assert provider.is_booted is False

    def test_reset_from_booted(self) -> None:
        provider = _ProbeProvider()
        provider._state = ProviderState.BOOTED
        assert provider.is_booted is True

        provider.reset_state()

        assert provider.state == ProviderState.CREATED
        assert provider.is_booted is False

    def test_reset_from_shutdown(self) -> None:
        provider = _ProbeProvider()
        provider._state = ProviderState.SHUTDOWN

        provider.reset_state()

        assert provider.state == ProviderState.CREATED

    def test_reset_from_registered(self) -> None:
        provider = _ProbeProvider()
        provider._state = ProviderState.REGISTERED

        provider.reset_state()

        assert provider.state == ProviderState.CREATED

    def test_reset_is_idempotent(self) -> None:
        provider = _ProbeProvider()
        provider.reset_state()
        provider.reset_state()
        assert provider.state == ProviderState.CREATED

    @pytest.mark.asyncio
    async def test_reset_provider_boots_again(self) -> None:
        """A reset provider goes through the register/boot phases again."""
        provider = _ProbeProvider()
        container = Container()
        orchestrator = ProviderOrchestrator(container)

        orchestrator.add(provider)
        await orchestrator.register_all(container)
        assert provider.state == ProviderState.REGISTERED

        provider._state = ProviderState.SHUTDOWN  # simulate a full cycle
        provider.reset_state()
        assert provider.state == ProviderState.CREATED
