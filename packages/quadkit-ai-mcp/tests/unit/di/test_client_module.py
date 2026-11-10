"""Unit tests for MCP client module and provider lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.ai.mcp.client.module import (
    MCPClientModule,
    MCPClientProvider,
    MCPConnection,
)
from quadkit.ai.mcp.config import MCPConfig


class TestMCPClientModule:
    """Test MCPClientModule functionality."""

    def test_module_creation(self) -> None:
        """Test module can be created."""
        conn = MCPConnection.sse("http://localhost:8000/mcp", name="test")
        module = MCPClientModule.configure([conn])
        assert module is not None

    def test_module_with_connections(self) -> None:
        """Test module creation with connections."""
        conn = MCPConnection.sse("http://localhost:8000/mcp", name="test")
        module = MCPClientModule.configure([conn])
        assert module is not None

    @pytest.mark.asyncio
    async def test_module_providers(self) -> None:
        """Test module returns correct providers."""
        conn = MCPConnection.sse("http://localhost:8000/mcp", name="test")
        module = MCPClientModule.configure([conn])
        providers = module.providers()
        assert len(providers) == 1

        provider = providers[0]
        mock_container = MagicMock()
        await provider.register(mock_container)

        # Should register MCPClientRegistry and MCPClient
        assert mock_container.singleton.call_count == 2


class TestMCPClientProviderLifecycle:
    """Test MCP client provider lifecycle behaviors."""

    @pytest.mark.asyncio
    async def test_shutdown_disconnects_registered_clients(self) -> None:
        """shutdown() should disconnect all clients created during register()."""
        provider = MCPClientProvider(
            connections=[
                MCPConnection.sse("http://localhost:8000/mcp", name="one"),
                MCPConnection.sse("http://localhost:8001/mcp", name="two"),
            ]
        )
        container = MagicMock()

        client_one = AsyncMock()
        client_two = AsyncMock()
        with patch.object(
            MCPConnection,
            "build_client",
            side_effect=[client_one, client_two],
        ):
            await provider.register(container)

        await provider.shutdown()

        client_one.disconnect.assert_awaited_once()
        client_two.disconnect.assert_awaited_once()


class TestMCPClientModuleConfiguration:
    """Test MCP client module configuration."""

    def test_config_defaults(self) -> None:
        """Test default configuration values."""
        config = MCPConfig()
        assert config.client_url is None
        assert config.request_timeout == 30.0

    def test_config_with_values(self) -> None:
        """Test configuration with custom values."""
        config = MCPConfig(
            client_url="http://localhost:8000/mcp",
            request_timeout=60.0,
        )
        assert config.client_url == "http://localhost:8000/mcp"
        assert config.request_timeout == 60.0
