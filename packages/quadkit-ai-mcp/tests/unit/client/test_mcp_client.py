"""Unit tests for MCP client initialization."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.mcp.client.core import MCPClient
from quadkit.ai.mcp.exceptions import MCPInitializationError


class TestMCPClientInitialization:
    """Tests for MCPClient initialization behavior."""

    @pytest.fixture
    def mock_transport(self) -> MagicMock:
        """Create a mock transport."""
        transport = MagicMock()
        transport.connect = AsyncMock()
        transport.disconnect = AsyncMock()
        transport.send = AsyncMock()
        transport.receive = AsyncMock()
        return transport

    @pytest.mark.asyncio
    async def test_client_initialization_sets_initialized(
        self, mock_transport: MagicMock
    ) -> None:
        """Test that connect() sets the initialized flag."""
        mock_transport.receive = AsyncMock(
            return_value={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "serverInfo": {"name": "test-server", "version": "1.0.0"},
                },
            }
        )

        client = MCPClient(transport=mock_transport)
        assert client._initialized is False

        await client.connect()

        assert client._initialized is True

    @pytest.mark.asyncio
    async def test_list_tools_fails_if_not_initialized(
        self, mock_transport: MagicMock
    ) -> None:
        """Test that list_tools raises before connect."""
        client = MCPClient(transport=mock_transport)

        with pytest.raises(MCPInitializationError) as exc_info:
            await client.list_tools()

        assert "not initialized" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_call_tool_fails_if_not_initialized(
        self, mock_transport: MagicMock
    ) -> None:
        """Test that call_tool raises before connect."""
        client = MCPClient(transport=mock_transport)

        with pytest.raises(MCPInitializationError) as exc_info:
            await client.call_tool("test_tool", {})

        assert "not initialized" in str(exc_info.value).lower()
