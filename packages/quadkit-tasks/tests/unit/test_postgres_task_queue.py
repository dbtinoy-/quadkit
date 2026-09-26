"""Integration tests for the Postgres task queue (requires TEST_POSTGRES_DSN).

These run against a real Postgres instance through the current
provider-injected API (``PostgresTaskQueue(provider=...)``). Skipped when
``TEST_POSTGRES_DSN`` is unset or asyncpg/quadkit-sql are unavailable.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

pytestmark = [
    pytest.mark.integration,
    pytest.mark.asyncio,
]

from quadkit.tasks.backends.postgres import (  # noqa: E402
    PostgresTaskConfig,
    PostgresTaskQueue,
)
from quadkit.tasks.models.job import JobProtocol  # noqa: E402

TEST_DSN = os.environ.get("TEST_POSTGRES_DSN")
TABLE = "qk_tasks_test_queue"


@pytest_asyncio.fixture
async def pg_queue() -> AsyncIterator[PostgresTaskQueue]:
    if not TEST_DSN:
        pytest.skip("TEST_POSTGRES_DSN not set; skipping Postgres integration tests")
    pytest.importorskip("asyncpg")
    from quadkit.sql.providers.postgres_provider import PostgresProvider

    provider = PostgresProvider(TEST_DSN)
    await provider.connect()

    # Start from a clean slate (the queue auto-creates the table).
    async with provider.scoped_context():
        conn = await provider.get_scoped_connection()
        await conn.execute(f"DROP TABLE IF EXISTS {TABLE}")  # noqa: S608

    queue = PostgresTaskQueue(
        config=PostgresTaskConfig(dsn=TEST_DSN, table=TABLE),
        provider=provider,
    )
    try:
        yield queue
    finally:
        async with provider.scoped_context():
            conn = await provider.get_scoped_connection()
            await conn.execute(f"DROP TABLE IF EXISTS {TABLE}")  # noqa: S608
        await provider.disconnect()


def _job(kwargs: dict[str, object] | None = None) -> JobProtocol:
    """Build a JobProtocol for enqueueing."""
    return JobProtocol(name="test_task", kwargs=kwargs or {})


async def test_enqueue_dequeue_ack_roundtrip(pg_queue: PostgresTaskQueue) -> None:
    """Enqueue, dequeue, and ack a job end to end."""
    job = _job(kwargs={"task": "send_email", "to": "a@example.com"})
    enqueued = await pg_queue.enqueue(job)
    assert enqueued.is_ok()
    job_id = enqueued.unwrap()

    item = await pg_queue.dequeue()
    assert item is not None
    assert item.id == job_id
    assert item.name == "send_email" or item.kwargs.get("task") == "send_email"

    await pg_queue.ack(job_id)
    assert await pg_queue.get_task_count() == 0


async def test_visibility_timeout_requeues_task(pg_queue: PostgresTaskQueue) -> None:
    """A stalled in-progress task is requeued after the visibility window."""
    job = _job(kwargs={"task": "retry_me"})
    assert (await pg_queue.enqueue(job)).is_ok()

    item = await pg_queue.dequeue()
    assert item is not None

    # Let the visibility window elapse, then sweep stalled tasks.
    await asyncio.sleep(1.1)
    affected = await pg_queue.requeue_stalled(1)
    assert affected >= 1

    # Another worker can now dequeue the same job.
    item2 = await pg_queue.dequeue()
    assert item2 is not None
    assert item2.id == item.id
    await pg_queue.ack(item.id)


async def test_nack_with_delay_respects_available_at(pg_queue: PostgresTaskQueue) -> None:
    """nack() delays the task's availability; it is not dequeued in the meantime."""
    job = _job(kwargs={"task": "delay_me"})
    assert (await pg_queue.enqueue(job)).is_ok()

    item = await pg_queue.dequeue()
    assert item is not None
    await pg_queue.nack(item.id)  # immediate requeue by default

    # Re-queue with a delay via the internal API (public nack takes requeue only).
    await pg_queue.dequeue()
    await pg_queue._nack(item.id, requeue=True, delay_seconds=2)

    assert await pg_queue.dequeue() is None

    await asyncio.sleep(2.1)
    item2 = await pg_queue.dequeue()
    assert item2 is not None
    assert item2.id == item.id
    await pg_queue.ack(item.id)


async def test_nack_without_requeue_marks_failed(pg_queue: PostgresTaskQueue) -> None:
    """nack(requeue=False) must NOT make the task available again."""
    job = _job(kwargs={"task": "drop_me"})
    assert (await pg_queue.enqueue(job)).is_ok()

    item = await pg_queue.dequeue()
    assert item is not None
    await pg_queue.nack(item.id, requeue=False)

    # The task is terminal, not pending.
    assert await pg_queue.dequeue() is None
    status = await pg_queue.get_task_status(item.id)
    assert status == "failed"


async def test_max_attempts_moves_task_to_failed(pg_queue: PostgresTaskQueue) -> None:
    """A stalled task past max_attempts is marked failed, not requeued."""
    pg_queue.config.max_attempts = 1

    job = _job(kwargs={"task": "will_fail"})
    assert (await pg_queue.enqueue(job)).is_ok()

    item = await pg_queue.dequeue()  # attempts -> 1
    assert item is not None
    await asyncio.sleep(1.1)
    await pg_queue.requeue_stalled(1)

    status = await pg_queue.get_task_status(item.id)
    assert status == "failed"

    # Failed tasks are not dequeued.
    assert await pg_queue.dequeue() is None


async def test_concurrent_dequeue_returns_unique_tasks(pg_queue: PostgresTaskQueue) -> None:
    """Concurrent dequeues never hand the same task to two workers."""
    ids = []
    for i in range(5):
        job = _job(kwargs={"task": f"job_{i}"})
        assert (await pg_queue.enqueue(job)).is_ok()

    results = await asyncio.gather(*(pg_queue.dequeue() for _ in range(8)))
    dequeued = [r for r in results if r is not None]

    # No duplicates: each task is handed out at most once.
    for r in dequeued:
        assert r.id not in ids
        ids.append(r.id)
    assert len(ids) <= 5
