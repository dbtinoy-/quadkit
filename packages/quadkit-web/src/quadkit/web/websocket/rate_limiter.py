"""WebSocket message rate limiter.

Implements a per-connection token-bucket rate limiter for WebSocket messages.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from quadkit.primitives import clock as ambient_clock


@dataclass
class _BucketState:
    """Token-bucket state for a single connection."""

    tokens: float
    last_refill: float = 0.0


class WebSocketRateLimiter:
    """Per-connection token-bucket rate limiter for WebSocket messages.

    Each connection gets its own token bucket that refills at ``max_messages_per_second``
    tokens per second. An incoming message consumes one token. If the bucket is empty
    the message is rejected and ``check()`` returns ``False``.

    State for connections that have been cleaned up via ``remove()`` is discarded
    automatically.

    Attributes:
        max_messages_per_second: Maximum sustained message rate per connection.

    Example:
        ```python
        limiter = WebSocketRateLimiter(max_messages_per_second=10.0)
        connection_id_manager = get_connection_id_manager()

        async def on_message(self, websocket, message):
            conn_id = connection_id_manager.get_or_create(websocket)
            if not await limiter.check(conn_id):
                await websocket.send_json({"type": "error", "error": "rate_limit_exceeded"})
                return
            ...
        ```
    """

    def __init__(
        self,
        max_messages_per_second: float = 10.0,
    ) -> None:
        """Initialise the rate limiter.

        Args:
            max_messages_per_second: Maximum number of messages per second per connection.
                Must be a positive number.
        """
        if max_messages_per_second <= 0:
            raise ValueError("max_messages_per_second must be positive")
        self._max_rate = max_messages_per_second
        self._connections: dict[str, _BucketState] = {}
        self._lock = asyncio.Lock()

    async def check(self, connection_id: str) -> bool:
        """Check whether a message from ``connection_id`` is within the rate limit.

        Refills the token bucket proportionally to elapsed time, then attempts
        to consume one token.  Returns ``True`` if the message is allowed,
        ``False`` if the rate limit is exceeded.

        Args:
            connection_id: A unique identifier for the connection (UUID string).

        Returns:
            True if the message is allowed; False if rate-limited.
        """
        now = ambient_clock.monotonic()

        async with self._lock:
            if connection_id not in self._connections:
                # New connection: start with a full bucket
                self._connections[connection_id] = _BucketState(
                    tokens=self._max_rate,
                    last_refill=now,
                )

            bucket = self._connections[connection_id]

            # Refill tokens based on elapsed time
            elapsed = now - bucket.last_refill
            bucket.tokens = min(
                self._max_rate,
                bucket.tokens + elapsed * self._max_rate,
            )
            bucket.last_refill = now

            if bucket.tokens < 1.0:
                return False

            bucket.tokens -= 1.0
            return True

    async def remove(self, connection_id: str) -> None:
        """Remove tracking state for a connection.

        Call this when a WebSocket connection closes to free memory.

        Args:
            connection_id: The same identifier passed to ``check()``.
        """
        async with self._lock:
            self._connections.pop(connection_id, None)

    @property
    def active_connection_count(self) -> int:
        """Number of connections currently being tracked."""
        return len(self._connections)


__all__ = ["WebSocketRateLimiter"]
