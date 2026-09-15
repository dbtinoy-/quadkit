# quadkit-contracts/src/quadkit/contracts/queue/protocols.py
"""Queue and consumer protocols."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from quadkit.contracts.core.health import HealthCheckResult
    from quadkit.contracts.queue.types import BusMessage


@runtime_checkable
class QueueProtocol(Protocol):
    """Structural protocol for message queue / bus backends.

    Implementations include in-memory, Redis Pub/Sub, RabbitMQ, Kafka,
    and SQS.  ``connect()`` / ``close()`` manage the connection lifecycle;
    ``publish()`` and ``subscribe()`` handle message delivery.
    """

    async def connect(self) -> None:
        """Establish connection to the broker."""
        ...

    async def close(self) -> None:
        """Close the connection and release resources."""
        ...

    async def publish(self, topic: str, message: BusMessage) -> None:
        """Publish a message to a topic.

        Args:
            topic: Destination topic or queue name.
            message: The message to publish.

        Raises:
            QueueError: For expected publish failures (quota, auth, etc.).
        """
        ...

    async def subscribe(
        self,
        topic: str,
        handler: Callable[[BusMessage], Coroutine[Any, Any, None]],
    ) -> None:
        """Subscribe a handler to a topic.

        The handler is called for each message received.  The backend is
        responsible for acknowledging or rejecting messages.

        Args:
            topic: Topic or queue name to subscribe to.
            handler: Async callable invoked per message.
        """
        ...

    async def health_check(self, timeout: float = 5.0) -> HealthCheckResult:
        """Check broker connectivity."""
        ...


@runtime_checkable
class MessageConsumerProtocol(Protocol):
    """Protocol for consumer worker classes.

    Consumer workers register topic subscriptions and run the event loop.
    """

    async def start(self) -> None:
        """Start consuming messages from subscribed topics."""
        ...

    async def stop(self) -> None:
        """Stop consuming and drain in-flight messages."""
        ...


__all__ = ["MessageConsumerProtocol", "QueueProtocol"]
