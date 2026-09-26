"""RabbitMQ task queue implementation

This module provides a RabbitMQ-based task queue using AMQP protocol.
Suitable for production deployments requiring high reliability and message delivery guarantees.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.result import Ok, Result
from quadkit.serialization import dumps, loads
from quadkit.tasks.exceptions import TaskError
from quadkit.tasks.hooks import TaskEnqueuedHook

# Optional RabbitMQ dependency
try:
    import aio_pika

    HAS_RABBITMQ = True
except ImportError:
    HAS_RABBITMQ = False
    aio_pika = None

from typing import Any, cast

from quadkit.contracts.infra.tasks import TaskQueueProtocol

if TYPE_CHECKING:
    from quadkit.contracts.core import HookRegistryProtocol
from quadkit.tasks.models.job import JobProtocol


class RabbitMQTaskQueue(TaskQueueProtocol):
    """RabbitMQ-based task queue implementation

    Uses AMQP message queues with priority support for reliable
    message delivery and processing. Provides clustering and
    high-availability features through RabbitMQ.

    Characteristics:
    - Storage: AMQP message queues with priority support
    - Features: Message persistence, delivery guarantees, clustering
    - Use Case: Production messaging, high-throughput scenarios
    - Dependencies: aio-pika>=9.3.0

    Example:
        ```python
        queue = RabbitMQTaskQueue(
            amqp_url="amqp://localhost:5672/"
        )
        await queue.enqueue(task)
        task = await queue.dequeue()
        await queue.close()
        ```
    """

    def __init__(
        self,
        amqp_url: str = "amqp://localhost:5672/",
        queue_name: str = "tasks",
    ):
        """Initialize RabbitMQ task queue

        Args:
            amqp_url: AMQP connection URL
            queue_name: Name of the queue

        Raises:
            ImportError: If aio-pika package is not installed
        """
        if not HAS_RABBITMQ:
            raise ImportError(
                "aio-pika is required for RabbitMQ task queue. "
                "Install with: pip install quadkit-tasks[rabbitmq]",
            )

        self.amqp_url = amqp_url
        self.queue_name = queue_name
        # Use Any for these attributes to avoid tight dependency on aio-pika's concrete types
        self.connection: Any | None = None
        self.channel: Any | None = None
        self.queue: Any | None = None
        # Maps task_id → raw AMQP message for manual ack/nack
        self._in_flight: dict[str, Any] = {}
        self._hooks: HookRegistryProtocol | None = None

    def set_hook_registry(self, hooks: HookRegistryProtocol | None) -> None:
        """Attach an optional hook registry after provider boot wiring."""
        self._hooks = hooks

    async def _emit_action(self, hook_name: str, payload: object) -> None:
        """Emit a task action hook when a registry is available."""
        hooks = getattr(self, "_hooks", None)
        if hooks is None:
            return

        await hooks.call_action(hook_name, payload=payload)

    async def _ensure_connection(self) -> None:
        """Ensure RabbitMQ connection is established

        Creates connection, channel, and declares queue if not already done.
        Uses robust connection for automatic reconnection.
        """
        if not self.connection:
            # Connect and cast to Any to avoid tight reliance on aio-pika stubs in the type-checking
            self.connection = cast("Any", await aio_pika.connect_robust(self.amqp_url))
            self.channel = cast("Any", await self.connection.channel())

            # Declare queue with priority support
            self.queue = await cast("Any", self.channel).declare_queue(
                self.queue_name,
                durable=True,  # Survive broker restart
                arguments={"x-max-priority": 255},  # Enable priority
            )

    async def enqueue(self, task: JobProtocol) -> Result[str, TaskError]:  # type: ignore[override]
        """Add a task to the queue, returning Ok(task_id) or Err(TaskError) on failure.

        Publishes task as a persistent AMQP message with priority.

        Args:
            task: Task to enqueue

        Returns:
            Ok containing the enqueued task id, or Err containing a TaskError.
        """
        await self._ensure_connection()

        assert self.channel is not None  # noqa: S101  # set by _ensure_connection
        assert self.queue is not None  # noqa: S101  # set by _ensure_connection

        task_data: Any = dumps(task.to_dict())
        body = task_data.encode() if isinstance(task_data, str) else task_data

        # Use Any-typed constructors to avoid mypy call-arg mismatches with aio-pika stubs
        message_cls = cast("Any", aio_pika).Message
        delivery_mode_cls = getattr(aio_pika, "DeliveryMode", None)
        delivery_mode = (
            getattr(delivery_mode_cls, "PERSISTENT", None)
            if delivery_mode_cls is not None
            else None
        )

        message = message_cls(
            body=body,
            delivery_mode=delivery_mode,
            priority=min(task.priority, 255),  # RabbitMQ max priority is 255
        )

        await cast("Any", self.channel).default_exchange.publish(
            message,
            routing_key=self.queue_name,
        )
        await self._emit_action(
            "task.queued",
            TaskEnqueuedHook(task_name=task.name, queue_name=self.queue_name),
        )
        return Ok(task.id)

    async def dequeue(self) -> JobProtocol | None:
        """Remove and return the next task from the queue

        Consumes one message from the queue with acknowledgment.

        Returns:
            Next task or None if queue is empty
        """
        await self._ensure_connection()

        assert self.queue is not None  # noqa: S101  # set by _ensure_connection

        try:
            # Get one message with timeout
            message = await cast("Any", self.queue).get(timeout=1)
            if message:
                task_data = loads(message.body.decode())
                task = JobProtocol.from_dict(task_data)
                # Store message for explicit ack/nack — do NOT auto-ack here
                self._in_flight[task.id] = message
                return task
        except Exception as e:
            # aio-pika may or may not expose an 'exceptions.QueueEmpty' symbol in the installed stub; check at runtime.
            if hasattr(aio_pika, "exceptions") and isinstance(
                e,
                aio_pika.exceptions.QueueEmpty,
            ):
                pass
            else:
                raise

        return None

    async def ack(self, task_id: str) -> None:
        """Acknowledge successful processing of a dequeued task

        Sends a ``basic_ack`` to RabbitMQ, permanently committing
        the delivery.

        Args:
            task_id: ID of the task to acknowledge
        """
        message = self._in_flight.pop(task_id, None)
        if message is not None:
            await cast("Any", message).ack()

    async def nack(self, task_id: str, requeue: bool = True) -> None:
        """Negative-acknowledge a dequeued task, optionally requeuing it

        Sends a ``basic_nack`` to RabbitMQ. If ``requeue`` is True the
        broker returns the message to the queue for retry.

        Args:
            task_id: ID of the task to negative-acknowledge
            requeue: If True, requeue the message; if False, dead-letter it
        """
        message = self._in_flight.pop(task_id, None)
        if message is not None:
            await cast("Any", message).nack(requeue=requeue)

    async def get_task_count(self) -> int:
        """Get the number of tasks in the queue

        Returns:
            Number of pending messages in the queue
        """
        await self._ensure_connection()

        assert self.channel is not None  # noqa: S101  # set by _ensure_connection

        # Declare queue passively to get info without modifying it
        queue_info = await cast("Any", self.channel).declare_queue(
            self.queue_name,
            passive=True,
        )
        return int(cast("Any", queue_info).message_count)

    async def clear(self) -> None:
        """Clear all tasks from the queue

        Purges all messages from the queue.
        """
        await self._ensure_connection()
        assert self.queue is not None  # noqa: S101  # set by _ensure_connection
        await cast("Any", self.queue).purge()

    async def close(self) -> None:
        """Close the RabbitMQ connection

        Closes channel and connection to release resources. The references
        are cleared so a later call reconnects instead of reusing the
        closed connection (a closed object is still truthy).
        """
        if self.channel:
            await cast("Any", self.channel).close()
            self.channel = None
        if self.connection:
            await cast("Any", self.connection).close()
            self.connection = None
        self.queue = None
