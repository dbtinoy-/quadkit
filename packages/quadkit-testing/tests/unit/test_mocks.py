"""Tests for testing.mocks module."""

import pytest

from quadkit.di.container import Container
from quadkit.testing.mocks.base import MockProvider


class TestMockProvider:
    """Tests for MockProvider."""

    @pytest.mark.asyncio
    async def test_mock_provider_initialization(self) -> None:
        """Test MockProvider initializes with correct defaults."""
        provider = MockProvider()

        assert provider.name == "mock"
        assert provider._started is False
        assert provider._stopped is False

    @pytest.mark.asyncio
    async def test_mock_provider_register_noop(self) -> None:
        """Test MockProvider.register is a no-op."""
        provider = MockProvider()
        container = Container()

        # Should not raise
        await provider.register(container)

    @pytest.mark.asyncio
    async def test_mock_provider_boot_sets_started(self) -> None:
        """Test MockProvider.boot sets _started to True."""
        provider = MockProvider()
        container = Container()

        assert provider._started is False

        await provider.boot(container)

        assert provider._started is True

    @pytest.mark.asyncio
    async def test_mock_provider_shutdown_sets_stopped(self) -> None:
        """Test MockProvider.shutdown sets _stopped to True."""
        provider = MockProvider()

        assert provider._stopped is False

        await provider.shutdown()

        assert provider._stopped is True

    @pytest.mark.asyncio
    async def test_mock_provider_full_lifecycle(self) -> None:
        """Test full lifecycle of MockProvider."""
        provider = MockProvider()
        container = Container()

        # Initial state
        assert provider._started is False
        assert provider._stopped is False

        # Register
        await provider.register(container)

        # Boot
        await provider.boot(container)
        assert provider._started is True

        # Shutdown
        await provider.shutdown()
        assert provider._stopped is True

    @pytest.mark.asyncio
    async def test_mock_provider_started_property(self) -> None:
        """Test started property returns correct value."""
        provider = MockProvider()

        assert provider.started is False

        await provider.boot(Container())

        assert provider.started is True

    @pytest.mark.asyncio
    async def test_mock_provider_stopped_property(self) -> None:
        """Test stopped property returns correct value."""
        provider = MockProvider()

        assert provider.stopped is False

        await provider.shutdown()

        assert provider.stopped is True
