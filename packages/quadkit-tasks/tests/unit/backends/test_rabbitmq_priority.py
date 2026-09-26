"""Priority tests for RabbitMQTaskQueue (unit — mocked aio_pika).

RabbitMQ natively supports priority queues via the ``x-max-priority`` queue
argument.  The broker dequeues messages in descending priority order and
maintains FIFO within the same priority level automatically.

These tests verify that the implementation:
1. Declares the queue with ``x-max-priority`` so the broker activates priority mode.
2. Publishes each message with the task's ``priority`` field set.
3. Caps the priority at 255 (the RabbitMQ protocol maximum).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.tasks.models.job import JobProtocol


def _make_job(job_id: str, priority: int) -> JobProtocol:
    return JobProtocol(id=job_id, name=job_id, priority=priority)


def _build_mock_aio_pika() -> tuple[MagicMock, AsyncMock, AsyncMock, AsyncMock]:
    """Return (mock_module, mock_connection, mock_channel, mock_queue)."""
    mock_queue = AsyncMock()
    mock_queue.message_count = 0

    mock_exchange = AsyncMock()

    mock_channel = AsyncMock()
    mock_channel.declare_queue = AsyncMock(return_value=mock_queue)
    mock_channel.default_exchange = mock_exchange

    mock_connection = AsyncMock()
    mock_connection.channel = AsyncMock(return_value=mock_channel)

    mock_module = MagicMock()
    mock_module.connect_robust = AsyncMock(return_value=mock_connection)
    mock_module.Message = MagicMock(side_effect=lambda **kw: MagicMock(**kw))
    mock_module.DeliveryMode.PERSISTENT = "persistent"

    return mock_module, mock_connection, mock_channel, mock_queue


class TestRabbitMQTaskQueuePriority:
    """RabbitMQTaskQueue declares the queue for priority and publishes with priority."""

    @pytest.fixture
    def queue_and_mocks(self):
        """Build a RabbitMQTaskQueue backed by mocked aio_pika."""
        mock_module, mock_conn, mock_channel, mock_q = _build_mock_aio_pika()

        with patch.dict("sys.modules", {"aio_pika": mock_module}):
            # Force reload so the module-level try/except picks up the mock
            import importlib

            import quadkit.tasks.backends.rabbitmq as rmq_mod

            importlib.reload(rmq_mod)

            queue = rmq_mod.RabbitMQTaskQueue(
                amqp_url="amqp://localhost/", queue_name="test_prio"
            )
            queue.connection = mock_conn
            queue.channel = mock_channel
            queue.queue = mock_q

            yield queue, mock_module, mock_channel, mock_q

    # ------------------------------------------------------------------
    # Queue declaration
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_queue_declared_with_x_max_priority(self, queue_and_mocks) -> None:
        """_ensure_connection must declare the queue with x-max-priority."""
        mock_module, _, mock_channel, _ = _build_mock_aio_pika()

        with patch.dict("sys.modules", {"aio_pika": mock_module}):
            import importlib

            import quadkit.tasks.backends.rabbitmq as rmq_mod

            importlib.reload(rmq_mod)

            q = rmq_mod.RabbitMQTaskQueue(
                amqp_url="amqp://localhost/", queue_name="prio_q"
            )
            await q._ensure_connection()

        declare_calls = mock_channel.declare_queue.call_args_list
        assert declare_calls, "declare_queue was never called"
        _, kwargs = declare_calls[0]
        args_pos = declare_calls[0].args

        # The queue name should be "prio_q"
        assert "prio_q" in args_pos or kwargs.get("name") == "prio_q"

        # x-max-priority must be present in the arguments dict
        arguments = kwargs.get("arguments") or (
            declare_calls[0].args[1] if len(declare_calls[0].args) > 1 else {}
        )
        assert "x-max-priority" in arguments, (
            "Queue must be declared with x-max-priority argument to enable "
            "RabbitMQ native priority mode"
        )
        assert arguments["x-max-priority"] == 255

    # ------------------------------------------------------------------
    # Message priority on publish
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_enqueue_publishes_message_with_task_priority(
        self, queue_and_mocks
    ) -> None:
        """enqueue() must set the task's priority on the AMQP message."""
        queue, mock_module, mock_channel, _ = queue_and_mocks
        job = _make_job("high_prio", priority=10)

        await queue.enqueue(job)

        message_constructor_calls = mock_module.Message.call_args_list
        assert message_constructor_calls, "aio_pika.Message was never constructed"

        kw = message_constructor_calls[-1].kwargs
        assert kw.get("priority") == 10, (
            f"Message must carry priority=10, got priority={kw.get('priority')}"
        )

    @pytest.mark.asyncio
    async def test_enqueue_priority_caps_at_255(self, queue_and_mocks) -> None:
        """Priorities above 255 must be capped at 255 (AMQP protocol limit)."""
        queue, mock_module, _, _ = queue_and_mocks
        job = _make_job("overflow", priority=999)

        await queue.enqueue(job)

        kw = mock_module.Message.call_args_list[-1].kwargs
        assert kw.get("priority") == 255, (
            f"Priority must be capped at 255, got {kw.get('priority')}"
        )

    @pytest.mark.asyncio
    async def test_low_priority_message_gets_correct_priority(
        self, queue_and_mocks
    ) -> None:
        """LOW priority (0) must be forwarded as-is."""
        from quadkit.tasks.types import Priority

        queue, mock_module, _, _ = queue_and_mocks
        job = _make_job("background", priority=Priority.LOW)

        await queue.enqueue(job)

        kw = mock_module.Message.call_args_list[-1].kwargs
        assert kw.get("priority") == Priority.LOW

    @pytest.mark.asyncio
    async def test_critical_priority_message_gets_correct_priority(
        self, queue_and_mocks
    ) -> None:
        """CRITICAL priority (20) must be forwarded as-is."""
        from quadkit.tasks.types import Priority

        queue, mock_module, _, _ = queue_and_mocks
        job = _make_job("urgent", priority=Priority.CRITICAL)

        await queue.enqueue(job)

        kw = mock_module.Message.call_args_list[-1].kwargs
        assert kw.get("priority") == Priority.CRITICAL
