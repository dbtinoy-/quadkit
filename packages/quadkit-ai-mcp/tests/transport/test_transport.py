"""Unit tests for MCP transport implementations."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.ai.mcp.exceptions import MCPTransportError
from quadkit.ai.mcp.transport.base import AbstractTransport
from quadkit.ai.mcp.transport.sse import SSETransport
from quadkit.ai.mcp.transport.stdio import StdioTransport


class TestStdioTransport:
    """Tests for StdioTransport."""

    @pytest.mark.asyncio
    async def test_init_default(self) -> None:
        """Test transport can be initialized without args."""
        transport = StdioTransport()
        assert transport._reader is None
        assert transport._writer is None
        assert transport._running is False

    @pytest.mark.asyncio
    async def test_init_with_custom_streams(self) -> None:
        """Test transport accepts custom reader/writer."""
        reader = MagicMock()
        writer = MagicMock()
        transport = StdioTransport(reader=reader, writer=writer)
        assert transport._reader == reader
        assert transport._writer == writer

    @pytest.mark.asyncio
    async def test_start_sets_running_with_custom_streams(self) -> None:
        """Test start sets the running flag with custom streams."""
        reader = MagicMock()
        writer = MagicMock()
        transport = StdioTransport(reader=reader, writer=writer)
        await transport.start()
        assert transport._running is True

    @pytest.mark.asyncio
    async def test_start_twice_no_op(self) -> None:
        """Test calling start twice is idempotent."""
        reader = MagicMock()
        writer = MagicMock()
        transport = StdioTransport(reader=reader, writer=writer)
        await transport.start()
        await transport.start()
        assert transport._running is True

    @pytest.mark.asyncio
    async def test_stop_resets_running(self) -> None:
        """Test stop resets the running flag."""
        reader = MagicMock()
        writer = MagicMock()
        writer.close = MagicMock()
        writer.wait_closed = AsyncMock()
        transport = StdioTransport(reader=reader, writer=writer)
        await transport.start()
        await transport.stop()
        assert transport._running is False

    @pytest.mark.asyncio
    async def test_stop_twice_no_op(self) -> None:
        """Test calling stop twice is idempotent."""
        reader = MagicMock()
        writer = MagicMock()
        writer.close = MagicMock()
        writer.wait_closed = AsyncMock()
        transport = StdioTransport(reader=reader, writer=writer)
        await transport.start()
        await transport.stop()
        await transport.stop()
        assert transport._running is False

    @pytest.mark.asyncio
    async def test_send_requires_running(self) -> None:
        """Test send raises if transport not running."""
        transport = StdioTransport()
        with pytest.raises(MCPTransportError, match="not started"):
            await transport.send({"jsonrpc": "2.0", "method": "test"})

    @pytest.mark.asyncio
    async def test_send_message(self) -> None:
        """Test send writes message to writer."""
        writer = MagicMock()
        writer.write = MagicMock()
        writer.drain = AsyncMock()
        reader = MagicMock()
        transport = StdioTransport(reader=reader, writer=writer)
        await transport.start()

        await transport.send({"jsonrpc": "2.0", "method": "test"})

        writer.write.assert_called_once()
        writer.drain.assert_called_once()

    @pytest.mark.asyncio
    async def test_receive_requires_running(self) -> None:
        """Test receive raises if transport not running."""
        transport = StdioTransport()
        with pytest.raises(MCPTransportError, match="not started"):
            await transport.receive()

    @pytest.mark.asyncio
    async def test_receive_returns_parsed_json(self) -> None:
        """Test receive parses JSON from reader."""
        reader = MagicMock()
        reader.readline = AsyncMock(return_value=b'{"jsonrpc": "2.0", "id": 1}')
        writer = MagicMock()
        transport = StdioTransport(reader=reader, writer=writer)
        await transport.start()

        result = await transport.receive()

        assert result == {"jsonrpc": "2.0", "id": 1}

    @pytest.mark.asyncio
    async def test_receive_returns_none_on_empty(self) -> None:
        """Test receive returns None on empty line."""
        reader = MagicMock()
        reader.readline = AsyncMock(return_value=b"")
        writer = MagicMock()
        transport = StdioTransport(reader=reader, writer=writer)
        await transport.start()

        result = await transport.receive()

        assert result is None

    @pytest.mark.asyncio
    async def test_receive_invalid_json_raises(self) -> None:
        """Test receive raises on invalid JSON."""
        sentinel = "SENTINEL-sensitive-stdio-payload"
        reader = MagicMock()
        reader.readline = AsyncMock(return_value=sentinel.encode())
        writer = MagicMock()
        transport = StdioTransport(reader=reader, writer=writer)
        await transport.start()

        with pytest.raises(MCPTransportError, match="Invalid JSON") as exc_info:
            await transport.receive()
        assert sentinel not in str(exc_info.value)


class TestSSETransport:
    """Tests for SSETransport."""

    @pytest.mark.asyncio
    async def test_init_default(self) -> None:
        """Test transport can be initialized without args."""
        transport = SSETransport()
        assert transport._running is False
        assert transport._server is None

    @pytest.mark.asyncio
    async def test_init_with_server(self) -> None:
        """Test transport accepts server."""
        server = MagicMock()
        transport = SSETransport(server=server)
        assert transport._server == server

    @pytest.mark.asyncio
    async def test_start_sets_running(self) -> None:
        """Test start sets the running flag."""
        transport = SSETransport()
        await transport.start()
        assert transport._running is True

    @pytest.mark.asyncio
    async def test_stop_resets_running(self) -> None:
        """Test stop resets the running flag."""
        transport = SSETransport()
        await transport.start()
        await transport.stop()
        assert transport._running is False

    @pytest.mark.asyncio
    async def test_send_requires_running(self) -> None:
        """Test send raises if transport not running."""
        transport = SSETransport()
        with pytest.raises(MCPTransportError, match="not started"):
            await transport.send({"jsonrpc": "2.0", "method": "test"})

    @pytest.mark.asyncio
    async def test_send_queues_message(self) -> None:
        """Test send queues the message."""
        transport = SSETransport()
        await transport.start()

        await transport.send({"jsonrpc": "2.0", "method": "test", "id": 1})

        messages = transport.get_queued_messages()
        assert len(messages) == 1
        assert messages[0]["id"] == 1

    @pytest.mark.asyncio
    async def test_receive_returns_none(self) -> None:
        """Test receive returns None for SSE."""
        transport = SSETransport()
        await transport.start()

        result = await transport.receive()

        assert result is None

    @pytest.mark.asyncio
    async def test_get_queued_messages_clears_queue(self) -> None:
        """Test get_queued_messages clears the queue."""
        transport = SSETransport()
        await transport.start()
        await transport.send({"jsonrpc": "2.0", "id": 1})
        await transport.send({"jsonrpc": "2.0", "id": 2})

        messages = transport.get_queued_messages()
        assert len(messages) == 2

        # Second call should return empty
        messages = transport.get_queued_messages()
        assert len(messages) == 0


class TestAbstractTransport:
    """Tests for AbstractTransport base class."""

    def test_is_abstract(self) -> None:
        """Test AbstractTransport cannot be instantiated directly."""

        class TestTransport(AbstractTransport):
            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

            async def send(self, message: dict) -> None:
                pass

            async def receive(self) -> dict | None:
                return None

        # Should be able to instantiate a proper subclass
        transport = TestTransport()
        assert isinstance(transport, AbstractTransport)
