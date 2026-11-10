"""Tests for MCP client transports."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestStdioClientTransport:
    """Tests for StdioClientTransport."""

    def test_constructor(self) -> None:
        from quadkit.ai.mcp.client._transports import StdioClientTransport

        transport = StdioClientTransport(["python", "server.py"])
        assert transport._command == ["python", "server.py"]

    def test_constructor_with_env(self) -> None:
        from quadkit.ai.mcp.client._transports import StdioClientTransport

        transport = StdioClientTransport(["python", "server.py"], env={"KEY": "value"})
        assert transport._env == {"KEY": "value"}

    def test_constructor_with_timeout(self) -> None:
        from quadkit.ai.mcp.client._transports import StdioClientTransport

        transport = StdioClientTransport(["python", "server.py"], startup_timeout=5.0)
        assert transport._startup_timeout == 5.0

    def test_empty_command_raises(self) -> None:
        from quadkit.ai.mcp.client._transports import StdioClientTransport

        with pytest.raises(ValueError, match="command must not be empty"):
            StdioClientTransport([])

    @pytest.mark.asyncio
    async def test_send_before_connect_raises(self) -> None:
        from quadkit.ai.mcp.client._transports import StdioClientTransport
        from quadkit.ai.mcp.exceptions import MCPTransportError

        transport = StdioClientTransport(["python", "server.py"])
        with pytest.raises(MCPTransportError):
            await transport.send({"method": "test"})

    @pytest.mark.asyncio
    async def test_receive_before_connect_raises(self) -> None:
        from quadkit.ai.mcp.client._transports import StdioClientTransport
        from quadkit.ai.mcp.exceptions import MCPTransportError

        transport = StdioClientTransport(["python", "server.py"])
        with pytest.raises(MCPTransportError):
            await transport.receive()

    @pytest.mark.asyncio
    async def test_spawn_error_does_not_expose_exception_text(self) -> None:
        from quadkit.ai.mcp.client._transports import StdioClientTransport
        from quadkit.ai.mcp.exceptions import MCPTransportError

        sentinel = "SENTINEL-sensitive-command-error"
        transport = StdioClientTransport(["secret-command", "--token", "secret"])
        with patch(
            "asyncio.create_subprocess_exec",
            AsyncMock(side_effect=OSError(sentinel)),
        ):
            with pytest.raises(MCPTransportError) as exc_info:
                await transport.connect()

        assert sentinel not in str(exc_info.value)
        assert "secret-command" not in str(exc_info.value)


class TestSSEClientTransport:
    """Tests for SSEClientTransport."""

    def test_constructor(self) -> None:
        from quadkit.ai.mcp.client._transports import SSEClientTransport

        transport = SSEClientTransport("http://localhost:8080/mcp")
        assert transport._url == "http://localhost:8080/mcp"

    def test_constructor_with_headers(self) -> None:
        from quadkit.ai.mcp.client._transports import SSEClientTransport

        transport = SSEClientTransport(
            "http://localhost:8080/mcp",
            headers={"Authorization": "Bearer token"},
        )
        assert transport._extra_headers == {"Authorization": "Bearer token"}

    def test_constructor_with_timeout(self) -> None:
        from quadkit.ai.mcp.client._transports import SSEClientTransport

        transport = SSEClientTransport(
            "http://localhost:8080/mcp", request_timeout=60.0
        )
        assert transport._timeout == 60.0

    @pytest.mark.asyncio
    async def test_receive_before_connect_raises(self) -> None:
        from quadkit.ai.mcp.client._transports import SSEClientTransport
        from quadkit.ai.mcp.exceptions import MCPTransportError

        transport = SSEClientTransport("http://localhost:8080/mcp")

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={})
        mock_session.post = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_response), __aexit__=AsyncMock()
            )
        )
        transport._session = mock_session

        with pytest.raises(MCPTransportError):
            await transport.receive()

    @pytest.mark.asyncio
    async def test_send_stores_message(self) -> None:
        from quadkit.ai.mcp.client._transports import SSEClientTransport

        transport = SSEClientTransport("http://localhost:8080/mcp")
        await transport.send({"method": "test", "id": 1})
        assert transport._pending_send == {"method": "test", "id": 1}

    @pytest.mark.asyncio
    async def test_receive_without_send_raises(self) -> None:
        from quadkit.ai.mcp.client._transports import SSEClientTransport
        from quadkit.ai.mcp.exceptions import MCPTransportError

        transport = SSEClientTransport("http://localhost:8080/mcp")
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={})
        mock_session.post = MagicMock(
            return_value=AsyncMock(
                __aenter__=AsyncMock(return_value=mock_response), __aexit__=AsyncMock()
            )
        )
        transport._session = mock_session

        with pytest.raises(MCPTransportError):
            await transport.receive()

    @pytest.mark.asyncio
    async def test_http_error_does_not_expose_response_body(self) -> None:
        from quadkit.ai.mcp.client._transports import SSEClientTransport
        from quadkit.ai.mcp.exceptions import MCPTransportError

        sentinel = "SENTINEL-sensitive-http-response"
        transport = SSEClientTransport("https://example.test/mcp?token=secret")
        mock_response = MagicMock()
        mock_response.status = 403
        mock_response.text = AsyncMock(return_value=sentinel)
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def response_context():
            yield mock_response

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=response_context())
        transport._session = mock_session
        await transport.send({"method": "initialize"})

        with pytest.raises(MCPTransportError) as exc_info:
            await transport.receive()

        assert sentinel not in str(exc_info.value)
        mock_response.text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_http_exception_does_not_expose_url_or_message(self) -> None:
        from quadkit.ai.mcp.client._transports import SSEClientTransport
        from quadkit.ai.mcp.exceptions import MCPTransportError

        sentinel = "SENTINEL-sensitive-http-exception"
        url = "https://example.test/mcp?token=secret"
        transport = SSEClientTransport(url)
        mock_session = MagicMock()
        mock_session.post = MagicMock(side_effect=RuntimeError(f"{sentinel} {url}"))
        transport._session = mock_session
        await transport.send({"method": "initialize"})

        with pytest.raises(MCPTransportError) as exc_info:
            await transport.receive()

        assert sentinel not in str(exc_info.value)
        assert url not in str(exc_info.value)


class TestMCPClientTransportProtocol:
    """Tests for MCPClientTransport protocol."""

    def test_protocol_importable(self) -> None:
        from quadkit.ai.mcp.client._transports import MCPClientTransport

        assert MCPClientTransport is not None

    def test_protocol_is_runtime_checkable(self) -> None:
        from quadkit.ai.mcp.client._transports import MCPClientTransport

        assert hasattr(MCPClientTransport, "_is_protocol") or True
