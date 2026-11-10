"""Unit tests for MCPClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.mcp.client.core import (
    MCPClient,
    MCPClientTransport,
    SSEClientTransport,
    StdioClientTransport,
)
from quadkit.ai.mcp.exceptions import (
    MCPInitializationError,
    MCPToolCallError,
)


class TestStdioClientTransport:
    """Tests for StdioClientTransport."""

    def test_init_with_command(self) -> None:
        """Test transport can be initialized with a command."""
        transport = StdioClientTransport(["uvx", "mcp-server-git"])
        assert transport._command == ["uvx", "mcp-server-git"]

    def test_init_with_empty_command_raises(self) -> None:
        """Test empty command raises ValueError."""
        with pytest.raises(ValueError, match="command must not be empty"):
            StdioClientTransport([])

    def test_init_with_env(self) -> None:
        """Test transport accepts custom environment."""
        env = {"CUSTOM_VAR": "value"}
        transport = StdioClientTransport(["uvx", "test"], env=env)
        assert transport._env == env

    def test_init_with_startup_timeout(self) -> None:
        """Test custom startup timeout is accepted."""
        transport = StdioClientTransport(["test"], startup_timeout=5.0)
        assert transport._startup_timeout == 5.0

    def test_protocol_runtime_checkable(self) -> None:
        """Test MCPClientTransport is runtime checkable."""
        assert isinstance(MCPClientTransport, type)
        # Should not raise for valid implementations
        mock_transport = MagicMock()
        mock_transport.connect = AsyncMock()
        mock_transport.disconnect = AsyncMock()
        mock_transport.send = AsyncMock()
        mock_transport.receive = AsyncMock()
        assert isinstance(mock_transport, MCPClientTransport)


class TestSSEClientTransport:
    """Tests for SSEClientTransport."""

    def test_init_with_url(self) -> None:
        """Test transport can be initialized with a URL."""
        transport = SSEClientTransport("http://localhost:8080/mcp")
        assert transport._url == "http://localhost:8080/mcp"

    def test_init_with_headers(self) -> None:
        """Test transport accepts custom headers."""
        headers = {"Authorization": "Bearer token123"}
        transport = SSEClientTransport("http://localhost:8080/mcp", headers=headers)
        assert transport._extra_headers == headers

    def test_init_with_timeout(self) -> None:
        """Test custom request timeout is accepted."""
        transport = SSEClientTransport(
            "http://localhost:8080/mcp", request_timeout=60.0
        )
        assert transport._timeout == 60.0


class TestMCPClient:
    """Tests for MCPClient."""

    @pytest.fixture
    def mock_transport(self) -> MagicMock:
        """Create a mock transport."""
        transport = MagicMock(spec=MCPClientTransport)
        transport.connect = AsyncMock()
        transport.disconnect = AsyncMock()
        transport.send = AsyncMock()
        transport.receive = AsyncMock()
        return transport

    @pytest.mark.asyncio
    async def test_client_init(self) -> None:
        """Test client can be initialized with a transport."""
        transport = StdioClientTransport(["test"])
        client = MCPClient(transport, request_timeout=30.0)
        assert client._transport == transport
        assert client._request_timeout == 30.0
        assert client._initialized is False

    @pytest.mark.asyncio
    async def test_client_connect_performs_handshake(
        self, mock_transport: MagicMock
    ) -> None:
        """Test connect performs MCP initialization handshake."""
        # Mock the initialize response
        mock_transport.receive.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "test-server", "version": "1.0.0"},
                "capabilities": {},
            },
        }

        client = MCPClient(mock_transport)
        await client.connect()

        mock_transport.connect.assert_awaited_once()
        assert client._initialized is True

    @pytest.mark.asyncio
    async def test_initialize_error_does_not_expose_server_message(
        self, mock_transport: MagicMock
    ) -> None:
        """Server-controlled error text must not escape the client boundary."""
        sentinel = "SENTINEL-sensitive-initialize-error"
        mock_transport.receive.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32000, "message": sentinel},
        }
        client = MCPClient(mock_transport)

        with pytest.raises(MCPInitializationError) as exc_info:
            await client.connect()

        assert sentinel not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_client_disconnect(self, mock_transport: MagicMock) -> None:
        """Test disconnect closes the transport."""
        client = MCPClient(mock_transport)
        await client.disconnect()
        mock_transport.disconnect.assert_awaited_once()
        assert client._initialized is False

    @pytest.mark.asyncio
    async def test_context_manager(self, mock_transport: MagicMock) -> None:
        """Test async context manager protocol."""
        mock_transport.receive.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "test", "version": "1.0.0"},
                "capabilities": {},
            },
        }

        async with MCPClient(mock_transport) as client:
            assert client._initialized is True

        mock_transport.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_list_tools_requires_initialization(
        self, mock_transport: MagicMock
    ) -> None:
        """Test list_tools raises if client not initialized."""
        client = MCPClient(mock_transport)
        with pytest.raises(MCPInitializationError, match="not initialized"):
            await client.list_tools()

    @pytest.mark.asyncio
    async def test_list_tools(self, mock_transport: MagicMock) -> None:
        """Test list_tools returns tools from server."""
        client = MCPClient(mock_transport)
        client._initialized = True
        mock_transport.receive.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "tools": [
                    {
                        "name": "test_tool",
                        "description": "A test tool",
                        "inputSchema": {"type": "object"},
                    }
                ]
            },
        }

        tools = await client.list_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "test_tool"

    @pytest.mark.asyncio
    async def test_invalid_protocol_response_does_not_echo_payload(
        self, mock_transport: MagicMock
    ) -> None:
        """Malformed responses must not leak their payload into exceptions."""
        from quadkit.ai.mcp.exceptions import MCPProtocolError

        sentinel = "SENTINEL-sensitive-response-payload"
        client = MCPClient(mock_transport)
        client._initialized = True
        mock_transport.receive.return_value = {
            "jsonrpc": "invalid-version",
            "id": 1,
            "result": {"message": sentinel},
        }

        with pytest.raises(MCPProtocolError) as exc_info:
            await client.list_tools()

        assert sentinel not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_call_tool(self, mock_transport: MagicMock) -> None:
        """Test call_tool invokes tool on server."""
        client = MCPClient(mock_transport)
        client._initialized = True
        mock_transport.receive.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"output": "tool result"},
        }

        result = await client.call_tool("test_tool", {"arg": "value"})
        assert result == {"output": "tool result"}

    @pytest.mark.asyncio
    async def test_call_tool_error_raises(self, mock_transport: MagicMock) -> None:
        """Test tool call errors raise MCPToolCallError."""
        client = MCPClient(mock_transport)
        client._initialized = True
        # Use error code -32000 (server error) instead of -32601 (method not found)
        sentinel = "SENTINEL-sensitive-server-error"
        mock_transport.receive.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"code": -32000, "message": sentinel},
        }

        with pytest.raises(MCPToolCallError) as exc_info:
            await client.call_tool("failing_tool", {})
        assert sentinel not in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_list_resources(self, mock_transport: MagicMock) -> None:
        """Test list_resources returns resources from server."""
        client = MCPClient(mock_transport)
        client._initialized = True
        mock_transport.receive.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "resources": [
                    {
                        "uri": "file:///test.txt",
                        "name": "test.txt",
                        "description": "A test file",
                        "mimeType": "text/plain",
                    }
                ]
            },
        }

        resources = await client.list_resources()
        assert len(resources) == 1
        assert resources[0]["uri"] == "file:///test.txt"

    @pytest.mark.asyncio
    async def test_list_prompts(self, mock_transport: MagicMock) -> None:
        """Test list_prompts returns prompts from server."""
        client = MCPClient(mock_transport)
        client._initialized = True
        mock_transport.receive.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "prompts": [
                    {
                        "name": "test_prompt",
                        "description": "A test prompt",
                        "arguments": [],
                    }
                ]
            },
        }

        prompts = await client.list_prompts()
        assert len(prompts) == 1
        assert prompts[0]["name"] == "test_prompt"
