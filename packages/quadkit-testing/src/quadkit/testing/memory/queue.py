"""In-memory queue backend for testing and compliance suites.

Provides :class:`InMemoryQueueBackend`, a lightweight dict/deque-backed
message queue backend implementing the enqueue/dequeue/ack/nack contract
used by :class:`~quadkit.testing.compliance.QueueBackendCompliance`.

Each instance is bound to a single queue name; creating a new instance
yields an isolated queue.  No external dependencies are required.
"""

from __future__ import annotations

import asyncio
from collections import deque
from typing import Any
from uuid import uuid4

__all__ = ["InMemoryQueueBackend"]


class InMemoryQueueBackend:
    """In-memory implementation of a message-level queue backend.

    Messages are plain dicts.  ``dequeue`` moves a message into the
    in-flight set; ``ack`` completes it, ``nack(requeue=True)`` puts it
    back at the front of the queue, and ``nack(requeue=False)`` discards
    it.

    Example::

        backend = InMemoryQueueBackend("orders")
        msg_id = await backend.enqueue({"type": "order.created"})
        message = await backend.dequeue()
        await backend.ack(message)
    """

    def __init__(self, queue_name: str = "default") -> None:
        """Initialise an isolated in-memory queue.

        Args:
            queue_name: Logical name of the queue this backend serves.
        """
        self._queue_name = queue_name
        self._pending: deque[dict[str, Any]] = deque()
        self._in_flight: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    @property
    def queue_name(self) -> str:
        """Logical name of the queue this backend serves."""
        return self._queue_name

    async def enqueue(self, payload: dict[str, Any]) -> str:
        """Enqueue a message and return its message ID.

        Args:
            payload: Message body (arbitrary JSON-serialisable mapping).

        Returns:
            Unique message ID string.
        """
        message_id = uuid4().hex
        async with self._lock:
            self._pending.append({"id": message_id, "payload": payload})
        return message_id

    async def dequeue(self) -> dict[str, Any] | None:
        """Dequeue the next pending message, if any.

        Returns:
            The message (a dict containing ``id`` and ``payload``) or
            ``None`` when the queue is empty.
        """
        async with self._lock:
            if not self._pending:
                return None
            message = self._pending.popleft()
            self._in_flight[message["id"]] = message
            return message

    async def ack(self, message: dict[str, Any]) -> None:
        """Acknowledge an in-flight message, completing its delivery.

        Args:
            message: Message previously returned by :meth:`dequeue`.
        """
        async with self._lock:
            self._in_flight.pop(str(message.get("id", "")), None)

    async def nack(self, message: dict[str, Any], *, requeue: bool = True) -> None:
        """Reject an in-flight message.

        Args:
            message: Message previously returned by :meth:`dequeue`.
            requeue: When ``True`` the message becomes available again;
                when ``False`` it is discarded permanently.
        """
        async with self._lock:
            self._in_flight.pop(str(message.get("id", "")), None)
            if requeue:
                self._pending.appendleft(message)

    async def size(self) -> int:
        """Return the number of pending (not yet dequeued) messages."""
        async with self._lock:
            return len(self._pending)
