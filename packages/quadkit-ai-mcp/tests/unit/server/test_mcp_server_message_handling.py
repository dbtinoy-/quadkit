"""Unit tests for MCP server message handling."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.mcp.server.core import MCPServer


class TestMCPServerMessageHandling:
    """Tests for MCPServer message handling."""

    @pytest.fixture
    def server(self) -> MCPServer:
        """Create an MCP server instance."""
        return MCPServer()

    @pytest.mark.asyncio
    async def test_invalid_jsonrpc_version_returns_error(
        self, server: MCPServer
    ) -> None:
        """Test that invalid JSON-RPC version returns error."""
        message = {
            "jsonrpc": "1.0",
            "id": 1,
            "method": "ping",
        }

        response = await server.handle_message(message)

        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert "error" in response
        assert response["error"]["code"] == -32600
        assert "Invalid JSON-RPC version" in response["error"]["message"]

    @pytest.mark.asyncio
    async def test_missing_method_returns_error(self, server: MCPServer) -> None:
        """Test that missing method field returns error."""
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "params": {},
        }

        response = await server.handle_message(message)

        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert "error" in response
        assert response["error"]["code"] == -32600
        assert "Missing method" in response["error"]["message"]

    @pytest.mark.asyncio
    async def test_method_not_found_returns_error(
        self, server: MCPServer
    ) -> None:
        """Test that unknown method name returns error."""
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "unknown/method",
        }

        response = await server.handle_message(message)

        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert "error" in response
        assert response["error"]["code"] == -32601
        assert "Method not found" in response["error"]["message"]

    @pytest.mark.asyncio
    async def test_handler_exception_returns_error(self, server: MCPServer) -> None:
        """Test that handler exception returns error."""
        tool_handler = MagicMock()
        tool_handler.list_tools = AsyncMock(
            side_effect=RuntimeError("Internal handler error")
        )

        server_with_handler = MCPServer(tool_handler=tool_handler, allow_unauthenticated=True)

        await server_with_handler.handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
        }

        response = await server_with_handler.handle_message(message)

        assert response is not None
        assert response["jsonrpc"] == "2.0"
        assert "error" in response
        assert response["error"]["code"] == -32603
        assert "Internal error" in response["error"]["message"]
