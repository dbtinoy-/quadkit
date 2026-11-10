"""HTTP+SSE transport for MCP server."""

from __future__ import annotations

from typing import Any

from quadkit.ai.mcp.transport.base import AbstractTransport
from quadkit.contracts.mcp.exceptions import MCPTransportError
from quadkit.logging import (
    get_logger,
)

logger = get_logger(__name__)


class SSETransport(AbstractTransport):
    """Server-Sent Events transport for MCP server.

    This transport uses HTTP POST for requests and SSE for streaming
    responses. Ideal for web-based integrations.
    """

    def __init__(
        self,
        server: Any | None = None,
    ) -> None:
        """Initialize the SSE transport.

        Args:
            server: Optional HTTP server instance.
        """
        self._server = server
        self._running = False
        self._message_queue: list[dict[str, Any]] = []

    async def start(self) -> None:
        """Start the SSE transport."""
        if self._running:
            return

        self._running = True
        logger.info("mcp_sse_transport_started")

    async def stop(self) -> None:
        """Stop the SSE transport."""
        if not self._running:
            return

        self._running = False
        logger.info("mcp_sse_transport_stopped")

    async def send(self, message: dict[str, Any]) -> None:
        """Send a message via SSE.

        Args:
            message: JSON-RPC message to send.

        Raises:
            MCPTransportError: If sending fails.
        """
        if not self._running:
            raise MCPTransportError(
                message="Transport not started",
                transport_type="sse",
            )

        # Queue the message for SSE delivery
        self._message_queue.append(message)
        logger.debug("mcp_sse_message_queued")

    async def receive(self) -> dict[str, Any] | None:
        """Receive is not applicable for SSE (pull-based).

        For HTTP+SSE, use the HTTP endpoint directly instead.

        Returns:
            None (receiving is handled via HTTP POST).
        """
        # For SSE transport, receiving happens via HTTP
        # This method is not used
        return None

    def get_queued_messages(self) -> list[dict[str, Any]]:
        """Get queued messages for SSE delivery.

        Returns:
            List of queued JSON-RPC messages.
        """
        messages = self._message_queue.copy()
        self._message_queue.clear()
        return messages


__all__ = ["SSETransport"]
