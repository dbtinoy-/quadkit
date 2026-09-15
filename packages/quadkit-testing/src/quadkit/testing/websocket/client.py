"""WebSocket test client for integration testing.

Provides a mock WebSocket connection that records sent/received messages
for assertion in tests without requiring an actual server connection.
"""

from __future__ import annotations

import asyncio
from typing import Any, Self


class WebSocketTestClient:
    """In-memory WebSocket test client for testing WebSocket handlers.

    Usage::

        async with WebSocketTestClient() as ws:
            await ws.send_json({"type": "subscribe", "channel": "order123"})
            response = await ws.receive_json()
            assert response["type"] == "subscribed"
    """

    def __init__(self) -> None:
        """Initialize the WebSocket test client."""
        self._send_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._receive_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._sent_messages: list[dict[str, Any]] = []
        self._received_messages: list[dict[str, Any]] = []
        self._connected: bool = False

    async def __aenter__(self) -> Self:
        """Connect the WebSocket."""
        self._connected = True
        return self

    async def __aexit__(self, *args: object) -> None:
        """Disconnect the WebSocket."""
        self._connected = False

    @property
    def is_connected(self) -> bool:
        """Whether the WebSocket is currently connected."""
        return self._connected

    @property
    def sent_messages(self) -> list[dict[str, Any]]:
        """All messages sent through this client."""
        return list(self._sent_messages)

    @property
    def received_messages(self) -> list[dict[str, Any]]:
        """All messages received by this client."""
        return list(self._received_messages)

    async def send_json(self, data: dict[str, Any]) -> None:
        """Send a JSON message through the WebSocket.

        Args:
            data: The JSON-serialisable message to send.
        """
        self._sent_messages.append(data)
        await self._send_queue.put(data)

    async def receive_json(self, timeout: float = 5.0) -> dict[str, Any]:
        """Receive a JSON message from the WebSocket.

        Args:
            timeout: Maximum time to wait for a message in seconds.

        Returns:
            The received JSON message.

        Raises:
            asyncio.TimeoutError: If no message is received within the timeout.
        """
        msg = await asyncio.wait_for(self._receive_queue.get(), timeout=timeout)
        self._received_messages.append(msg)
        return msg

    async def inject_response(self, data: dict[str, Any]) -> None:
        """Inject a response into the receive queue (for testing).

        Args:
            data: The response message to make available via receive_json.
        """
        await self._receive_queue.put(data)

    def assert_sent(self, expected: dict[str, Any]) -> None:
        """Assert that a specific message was sent.

        Args:
            expected: The expected message.

        Raises:
            AssertionError: If the message was not found.
        """
        assert expected in self._sent_messages, (
            f"Expected message not found in sent messages.\n"
            f"Expected: {expected}\n"
            f"Sent: {self._sent_messages}"
        )


__all__ = ["WebSocketTestClient"]
