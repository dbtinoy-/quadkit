"""Base transport for MCP server."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AbstractTransport(ABC):
    """Abstract base class for MCP transport implementations.

    A transport handles the I/O layer - reading requests and
    writing responses. The MCP server is transport-agnostic.
    """

    @abstractmethod
    async def start(self) -> None:
        """Start the transport."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the transport."""

    @abstractmethod
    async def send(self, message: dict[str, Any]) -> None:
        """Send a message through the transport.

        Args:
            message: JSON-RPC message to send.
        """

    @abstractmethod
    async def receive(self) -> dict[str, Any] | None:
        """Receive a message from the transport.

        Returns:
            Parsed JSON-RPC message, or None if no message available.
        """


__all__ = ["AbstractTransport"]
