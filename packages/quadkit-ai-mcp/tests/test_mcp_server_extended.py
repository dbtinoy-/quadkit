"""Tests for MCP server message handling."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestMCPServerMessageValidation:
    """Tests for server message validation."""

    @pytest.mark.asyncio
    async def test_invalid_jsonrpc_version(self) -> None:
        from quadkit.ai.mcp.server.core import MCPServer

        server = MCPServer()
        message = {"jsonrpc": "1.0", "id": 1, "method": "ping"}
        response = await server.handle_message(message)

        assert response is not None
        assert "error" in response
        assert response["error"]["code"] == -32600

    @pytest.mark.asyncio
    async def test_missing_method(self) -> None:
        from quadkit.ai.mcp.server.core import MCPServer

        server = MCPServer()
        message = {"jsonrpc": "2.0", "id": 1, "method": "nonexistent"}
        response = await server.handle_message(message)

        assert response is not None
        assert "error" in response
        assert response["error"]["code"] == -32601


class TestMCPServerToolHandler:
    """Tests for server with tool handler."""

    @pytest.mark.asyncio
    async def test_tools_list_with_handler(self) -> None:
        from quadkit.ai.mcp.server.core import MCPServer

        tool_handler = MagicMock()
        tool_handler.list_tools = AsyncMock(return_value={"tools": [{"name": "test"}]})
        server = MCPServer(tool_handler=tool_handler, allow_unauthenticated=True)

        await server.handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        message = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        response = await server.handle_message(message)

        assert response is not None
        assert "result" in response

    @pytest.mark.asyncio
    async def test_tools_call_with_handler(self) -> None:
        from quadkit.ai.mcp.server.core import MCPServer

        tool_handler = MagicMock()
        tool_handler.call_tool = AsyncMock(return_value={"content": [{"type": "text", "text": "ok"}]})
        server = MCPServer(tool_handler=tool_handler, allow_unauthenticated=True)

        await server.handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        message = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "test", "arguments": {}}}
        response = await server.handle_message(message)

        assert response is not None


class TestMCPServerResourceHandler:
    """Tests for server with resource handler."""

    @pytest.mark.asyncio
    async def test_resources_list_with_handler(self) -> None:
        from quadkit.ai.mcp.server.core import MCPServer

        resource_handler = MagicMock()
        resource_handler.list_resources = AsyncMock(return_value={"resources": []})
        server = MCPServer(resource_handler=resource_handler, allow_unauthenticated=True)

        await server.handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        message = {"jsonrpc": "2.0", "id": 1, "method": "resources/list"}
        response = await server.handle_message(message)

        assert response is not None
        assert "result" in response


class TestMCPServerPromptHandler:
    """Tests for server with prompt handler."""

    @pytest.mark.asyncio
    async def test_prompts_list_with_handler(self) -> None:
        from quadkit.ai.mcp.server.core import MCPServer

        prompt_handler = MagicMock()
        prompt_handler.list_prompts = AsyncMock(return_value={"prompts": []})
        server = MCPServer(prompt_handler=prompt_handler, allow_unauthenticated=True)

        await server.handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        message = {"jsonrpc": "2.0", "id": 1, "method": "prompts/list"}
        response = await server.handle_message(message)

        assert response is not None


class TestMCPServerSuccessResponse:
    """Tests for success responses."""

    def test_success_response_structure(self) -> None:
        from quadkit.ai.mcp.server.core import MCPServer

        server = MCPServer()
        response = server._success_response(1, {"data": "test"})

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert response["result"] == {"data": "test"}

    def test_error_response_structure(self) -> None:
        from quadkit.ai.mcp.server.core import MCPServer

        server = MCPServer()
        response = server._error_response(1, -32600, "Invalid request")

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "error" in response
        assert response["error"]["code"] == -32600


class TestMCPServerInitialize:
    """Tests for initialize flow."""

    @pytest.mark.asyncio
    async def test_initialize_with_client_info(self) -> None:
        from quadkit.ai.mcp.server.core import MCPServer

        server = MCPServer(name="test-server", version="2.0.0")
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"clientInfo": {"name": "test-client", "version": "1.0"}},
        }
        response = await server.handle_message(message)

        assert response is not None
        result = response["result"]
        assert result["serverInfo"]["name"] == "test-server"
        assert result["serverInfo"]["version"] == "2.0.0"


class TestMCPServerNotification:
    """Tests for notifications."""

    @pytest.mark.asyncio
    async def test_initialized_notification_no_response(self) -> None:
        from quadkit.ai.mcp.server.core import MCPServer

        server = MCPServer()
        message = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        response = await server.handle_message(message)

        assert response is None


class TestMCPServerExports:
    """Tests for server module exports."""

    def test_all_exported(self) -> None:
        from quadkit.ai.mcp.server import core

        expected = ["MCPServer"]
        for name in expected:
            assert hasattr(core, name)