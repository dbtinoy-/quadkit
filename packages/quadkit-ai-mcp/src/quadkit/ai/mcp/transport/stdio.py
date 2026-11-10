"""Stdio transport for MCP server."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from quadkit.ai.mcp.transport.base import AbstractTransport
from quadkit.contracts.mcp.exceptions import MCPTransportError
from quadkit.logging import (
    get_logger,
)
from quadkit.serialization import JSONDecodeError, dumps_str, loads

logger = get_logger(__name__)


class StdioTransport(AbstractTransport):
    """Stdio-based transport for MCP server.

    This transport reads JSON-RPC messages from stdin and writes
    responses to stdout. Ideal for CLI/desktop integration.
    """

    def __init__(
        self,
        reader: asyncio.StreamReader | None = None,
        writer: asyncio.StreamWriter | None = None,
    ) -> None:
        """Initialize the stdio transport.

        Args:
            reader: Optional stream reader (for testing).
            writer: Optional stream writer (for testing).
        """
        self._reader = reader
        self._writer = writer
        self._running = False

    async def start(self) -> None:
        """Start the stdio transport."""
        if self._running:
            return

        if self._reader is None:
            self._reader = asyncio.StreamReader()
            loop = asyncio.get_event_loop()
            protocol = asyncio.StreamReaderProtocol(self._reader)
            await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        if self._writer is None:
            _transport, self._writer = await asyncio.open_connection(
                sys.stdin.fileno(),  # type: ignore[arg-type]
                sys.stdout.fileno(),
            )

        self._running = True
        logger.info("mcp_stdio_transport_started")

    async def stop(self) -> None:
        """Stop the stdio transport."""
        if not self._running:
            return

        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()

        self._running = False
        logger.info("mcp_stdio_transport_stopped")

    async def send(self, message: dict[str, Any]) -> None:
        """Send a message through stdio.

        Args:
            message: JSON-RPC message to send.

        Raises:
            MCPTransportError: If sending fails.
        """
        if not self._running or self._writer is None:
            raise MCPTransportError(
                message="Transport not started",
                transport_type="stdio",
            )

        try:
            data = dumps_str(message) + "\n"
            self._writer.write(data.encode())
            await self._writer.drain()
        except Exception as e:  # noqa: BLE001 — any connect failure is a MCPTransportError
            raise MCPTransportError(
                message=f"Failed to send message ({type(e).__name__})",
                transport_type="stdio",
            ) from None

    async def receive(self) -> dict[str, Any] | None:
        """Receive a message from stdio.

        Returns:
            Parsed JSON-RPC message, or None if no data available.

        Raises:
            MCPTransportError: If receiving fails.
        """
        if not self._running or self._reader is None:
            raise MCPTransportError(
                message="Transport not started",
                transport_type="stdio",
            )

        try:
            # Read a line from stdin
            line = await self._reader.readline()
            if not line:
                return None

            decoded = line.decode()
            stripped = decoded.lstrip()
            if not stripped.startswith("{"):
                raise MCPTransportError(
                    message="Invalid JSON: expected object payload",
                    transport_type="stdio",
                )
            return loads(decoded)

        except MCPTransportError:
            raise
        except JSONDecodeError as e:
            raise MCPTransportError(
                message=f"Invalid JSON ({type(e).__name__})",
                transport_type="stdio",
            ) from None
        except Exception as e:  # noqa: BLE001 — any read/decode failure is a MCPTransportError
            raise MCPTransportError(
                message=f"Failed to receive message ({type(e).__name__})",
                transport_type="stdio",
            ) from None


__all__ = ["StdioTransport"]
