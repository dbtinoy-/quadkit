"""Tests for di/integration/provider.py - DiProvider."""

import pytest

from quadkit.di.integration.provider import DiProvider


class TestDiProvider:
    """Tests for DiProvider class."""

    def test_provider_name(self) -> None:
        """Test DiProvider has correct name."""
        provider = DiProvider()
        assert provider.name == "di"

    def test_provider_priority(self) -> None:
        """Test DiProvider has correct priority."""
        from quadkit.contracts.core.provider import ProviderPriority

        provider = DiProvider()
        assert provider.priority == ProviderPriority.INFRASTRUCTURE

    @pytest.mark.asyncio
    async def test_register_with_container(self) -> None:
        """Test register method with Container."""
        from quadkit.di.container import Container
        from quadkit.contracts.core.di import ContainerRegistrarProtocol

        provider = DiProvider()
        container = Container()
        await provider.register(container)

    @pytest.mark.asyncio
    async def test_boot_with_config(self) -> None:
        """Test boot with DiConfig."""
        from unittest.mock import AsyncMock, MagicMock

        provider = DiProvider()
        mock_container = MagicMock()
        mock_config = MagicMock()
        mock_config.type_hint_cache_size = 256

        from quadkit.di.config.models import DiConfig
        mock_container.resolve_optional = AsyncMock(return_value=mock_config)

        await provider.boot(mock_container)

    @pytest.mark.asyncio
    async def test_boot_without_config(self) -> None:
        """Test boot without DiConfig (uses defaults)."""
        from unittest.mock import AsyncMock, MagicMock

        provider = DiProvider()
        mock_container = MagicMock()
        mock_container.resolve_optional = AsyncMock(return_value=None)

        await provider.boot(mock_container)

    @pytest.mark.asyncio
    async def test_shutdown(self) -> None:
        """Test shutdown method."""
        provider = DiProvider()
        await provider.shutdown()
