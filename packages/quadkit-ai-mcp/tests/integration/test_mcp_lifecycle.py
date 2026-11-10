"""Integration tests for quadkit-ai-mcp package."""

from __future__ import annotations

import pytest

from quadkit.ai.mcp.config import MCPConfig
from quadkit.ai.mcp.di.provider import MCPProvider


class TestMCPProviderIntegration:
    """Integration tests for MCPProvider basic functionality."""

    @pytest.mark.integration
    def test_provider_initialization_default(self):
        """Test MCPProvider initialization with default config."""
        provider = MCPProvider()
        assert provider.name == "mcp"

    @pytest.mark.integration
    def test_provider_initialization_with_config(self):
        """Test MCPProvider initialization with custom config."""
        config = MCPConfig()
        provider = MCPProvider(config=config)
        assert provider.name == "mcp"

    @pytest.mark.integration
    def test_provider_has_required_attributes(self):
        """Test provider has required attributes."""
        provider = MCPProvider()
        assert hasattr(provider, "name")

    @pytest.mark.integration
    def test_provider_priority(self):
        """Test provider has correct priority."""
        from quadkit.contracts.core.provider import ProviderPriority
        provider = MCPProvider()
        assert provider.priority == ProviderPriority.PRESENTATION


class TestMCPConfigIntegration:
    """Integration tests for MCPConfig."""

    @pytest.mark.integration
    def test_mcp_config_creation(self):
        """Test MCPConfig can be created."""
        config = MCPConfig()
        assert config is not None

    @pytest.mark.integration
    def test_mcp_config_model_dump(self):
        """Test MCPConfig model can be serialized."""
        config = MCPConfig()
        config_dict = config.model_dump()
        assert isinstance(config_dict, dict)


class TestMCPModuleIntegration:
    """Integration tests for MCPModule."""

    @pytest.mark.integration
    def test_mcp_module_import(self):
        """Test MCPModule can be imported."""
        from quadkit.ai.mcp.module import MCPModule
        assert MCPModule is not None


class TestMCPServerIntegration:
    """Integration tests for MCP server."""

    @pytest.mark.integration
    def test_mcp_server_import(self):
        """Test MCPServer can be imported."""
        from quadkit.ai.mcp.server import MCPServer
        assert MCPServer is not None

    @pytest.mark.integration
    def test_mcp_server_handlers_import(self):
        """Test MCP handlers can be imported."""
        from quadkit.ai.mcp.server.handlers import (
            LoggingHandler,
            PromptHandler,
            ResourceHandler,
            ToolHandler,
        )
        assert LoggingHandler is not None
        assert PromptHandler is not None
        assert ResourceHandler is not None
        assert ToolHandler is not None


class TestMCPTransportIntegration:
    """Integration tests for MCP transports."""

    @pytest.mark.integration
    def test_sse_transport_import(self):
        """Test SSETransport can be imported."""
        from quadkit.ai.mcp.transport import SSETransport
        assert SSETransport is not None

    @pytest.mark.integration
    def test_stdio_transport_import(self):
        """Test StdioTransport can be imported."""
        from quadkit.ai.mcp.transport import StdioTransport
        assert StdioTransport is not None


class TestMCPClientIntegration:
    """Integration tests for MCP client."""

    @pytest.mark.integration
    def test_mcp_client_import(self):
        """Test MCPClient can be imported."""
        try:
            from quadkit.ai.mcp.client import MCPClient
            assert MCPClient is not None
        except ImportError:
            pytest.skip("MCPClient not available")


class TestMCPExceptionsIntegration:
    """Integration tests for MCP exceptions."""

    @pytest.mark.integration
    def test_mcp_exceptions_import(self):
        """Test MCP exceptions can be imported."""
        from quadkit.ai.mcp.exceptions import MCPInitializationError
        assert MCPInitializationError is not None