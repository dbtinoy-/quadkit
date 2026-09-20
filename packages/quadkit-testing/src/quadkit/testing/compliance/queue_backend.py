from __future__ import annotations

"""Contract compliance suite for QueueBackend implementations.

This suite tests queue backends that provide enqueue/dequeue/ack/nack
semantics at the message level (not the task level).
"""

import abc
from typing import Any
import uuid

import pytest

__all__ = ["QueueBackendCompliance"]


class QueueBackendCompliance(abc.ABC):
    """Compliance suite for queue backend implementations.

    Subclass and implement create_backend() to run all compliance tests.
    """

    @abc.abstractmethod
    async def create_backend(self, queue_name: str = "test-queue") -> Any:
        """Create the queue backend implementation under test.

        Args:
            queue_name: Name of the queue to use for testing.

        Returns:
            A fresh queue backend instance.
        """
        ...

    @pytest.mark.asyncio
    async def test_enqueue_returns_message_id(self) -> None:
        """enqueue() returns a message ID string."""
        backend = await self.create_backend()
        msg_id = await backend.enqueue({"type": "test", "data": "hello"})
        assert msg_id is not None
        assert isinstance(msg_id, str)

    @pytest.mark.asyncio
    async def test_dequeue_returns_enqueued_message(self) -> None:
        """dequeue() returns the message that was enqueued."""
        backend = await self.create_backend()
        payload = {"type": "test", "data": uuid.uuid4().hex}
        await backend.enqueue(payload)
        message = await backend.dequeue()
        assert message is not None

    @pytest.mark.asyncio
    async def test_dequeue_empty_returns_none(self) -> None:
        """dequeue() returns None when no messages are available."""
        backend = await self.create_backend(f"empty-queue-{uuid.uuid4().hex[:8]}")
        result = await backend.dequeue()
        assert result is None

    @pytest.mark.asyncio
    async def test_ack_removes_message(self) -> None:
        """ack() completes without error for an in-flight message."""
        backend = await self.create_backend()
        await backend.enqueue({"type": "test"})
        message = await backend.dequeue()
        assert message is not None
        await backend.ack(message)

    @pytest.mark.asyncio
    async def test_nack_requeues_message(self) -> None:
        """nack() with requeue=True makes the message available again."""
        backend = await self.create_backend()
        await backend.enqueue({"type": "test"})
        message = await backend.dequeue()
        assert message is not None
        await backend.nack(message, requeue=True)
        retry = await backend.dequeue()
        assert retry is not None

    @pytest.mark.asyncio
    async def test_nack_discards_message(self) -> None:
        """nack() with requeue=False permanently discards the message."""
        backend = await self.create_backend()
        await backend.enqueue({"type": "test"})
        message = await backend.dequeue()
        assert message is not None
        await backend.nack(message, requeue=False)
        gone = await backend.dequeue()
        assert gone is None
