"""Test task idempotency."""
from unittest.mock import AsyncMock

import pytest

from quadkit.contracts.exceptions import IdempotencyError, IdempotencyStoreError
from quadkit.result import Err, Ok
from quadkit.tasks.execution.manager import (
    IdempotencyManager,
    IdempotentTaskManager,
)
from quadkit.tasks.execution.worker import TaskWorker, TaskWorkerServices


class TestIdempotency:
    """Test task idempotency."""

    @pytest.mark.asyncio
    async def test_same_params_generate_same_key(self):
        """Test idempotency key generation is deterministic."""
        storage = AsyncMock()
        manager = IdempotencyManager(storage)

        key1 = manager.generate_key(
            "send_email", {"to": "user@test.com", "subject": "Hello"},
        )

        key2 = manager.generate_key(
            "send_email", {"to": "user@test.com", "subject": "Hello"},
        )

        assert key1 == key2

    @pytest.mark.asyncio
    async def test_different_params_generate_different_keys(self):
        """Test different params produce different keys."""
        storage = AsyncMock()
        manager = IdempotencyManager(storage)

        key1 = manager.generate_key("send_email", {"to": "user1@test.com"})

        key2 = manager.generate_key("send_email", {"to": "user2@test.com"})

        assert key1 != key2

    @pytest.mark.asyncio
    async def test_duplicate_task_returns_existing(self):
        """Test duplicate submission returns existing task."""
        storage = AsyncMock()
        storage.get.return_value = {
            "task_id": "existing_123",
            "idempotency_key": "key_abc",
            "status": "submitted",
            "created_at": "2024-01-01T00:00:00",
            "result": None,
        }

        queue = AsyncMock()
        idempotency = IdempotencyManager(storage)
        manager = IdempotentTaskManager(queue, idempotency)

        # Submit task
        result = await manager.submit_task(
            "process_payment", {"order_id": "123", "amount": 100},
        )

        # Should return existing task
        assert result.task_id == "existing_123"
        assert result.status == "submitted"

        # Should NOT enqueue new task
        queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_new_task_enqueued_and_recorded(self):
        """Test new task is enqueued and recorded."""
        storage = AsyncMock()
        storage.get.return_value = None  # No existing task

        queue = AsyncMock()
        idempotency = IdempotencyManager(storage)
        manager = IdempotentTaskManager(queue, idempotency)

        # Submit task
        result = await manager.submit_task("send_email", {"to": "user@test.com"})

        # Should create new task
        assert result.status == "submitted"
        assert result.task_id is not None

        # Should enqueue
        queue.enqueue.assert_called_once()

        # Should record in storage
        storage.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_client_provided_key(self):
        """Test client can provide custom idempotency key."""
        storage = AsyncMock()
        manager = IdempotencyManager(storage)

        key = manager.generate_key("task", {}, client_key="my-custom-key-123")

        assert key == "idempotency:my-custom-key-123"

    @pytest.mark.asyncio
    async def test_worker_skips_completed_task(self):
        """Test worker skips execution of already-completed tasks."""
        from unittest.mock import AsyncMock

        from quadkit.tasks.execution.worker import TaskWorker
        from quadkit.tasks.models.job import JobProtocol

        # Mock idempotency manager that returns completed task
        storage = AsyncMock()
        storage.get.return_value = {
            "task_id": "existing_123",
            "idempotency_key": "charge:123",
            "status": "completed",
            "created_at": "2024-01-01T00:00:00",
            "result": {"charged": True},
        }
        idempotency_manager = IdempotencyManager(storage)

        # Mock queue and handler
        queue = AsyncMock()
        handler = AsyncMock()

        # Create worker with idempotency manager
        worker = TaskWorker(
            "test-worker",
            queue,
            {"charge_payment": handler},
            services=TaskWorkerServices(idempotency_manager=idempotency_manager),
        )

        # Create job with idempotency key
        job = JobProtocol(id="job-1", name="charge_payment", idempotency_key="charge:123")

        # Execute job
        await worker._execute_job(job)

        # Verify handler was NOT called (skipped due to completion)
        handler.assert_not_called()

        # Verify job was marked as completed
        assert job.is_completed
        assert job.result.data == {"charged": True}


class TestIdempotencyRaceCondition:
    """Tests for the TOCTOU race condition in IdempotentTaskManager.submit_task (P1-4)."""

    @pytest.mark.asyncio
    async def test_concurrent_same_key_submissions_only_enqueue_once(self):
        """P1-4: Concurrent submissions with the same params must result in exactly 1 enqueue.

        The race: without a per-key lock, all N coroutines can pass check_duplicate
        before any of them calls record_submission, causing N duplicate enqueues.

        The fix: a per-key asyncio.Lock makes the check→enqueue→record sequence atomic.

        Mock design:
        - storage.get yields (asyncio.sleep(0)) so all coroutines advance past the
          check point before any reaches record_submission.
        - queue.enqueue also yields so the race window spans the full critical section.
        - storage.set is non-yielding so the record lands atomically once the lock
          is held.
        """
        import asyncio

        from unittest.mock import MagicMock

        from quadkit.tasks.execution.manager import IdempotencyManager, IdempotentTaskManager

        # --- Stateful in-memory storage ---
        store: dict = {}

        async def fake_get(key: str):
            await asyncio.sleep(0)  # yield → lets all coroutines reach this point
            return store.get(key)

        async def fake_set(key: str, value, ttl: float | None = None):
            # No yield: record is committed atomically once we reach this line.
            store[key] = value

        storage = MagicMock()
        storage.get = fake_get
        storage.set = fake_set

        # --- Counting queue ---
        enqueue_count = 0

        async def count_enqueue(task):
            nonlocal enqueue_count
            await asyncio.sleep(0)  # yield → keeps the race window open past check
            enqueue_count += 1

        queue = MagicMock()
        queue.enqueue = count_enqueue

        # --- Build manager under test ---
        idempotency_mgr = IdempotencyManager(storage=storage, ttl=3600)
        manager = IdempotentTaskManager(
            queue_client=queue,
            idempotency_manager=idempotency_mgr,
        )

        params = {"order_id": "ORD-001", "amount": 100}

        # Launch 10 concurrent submissions with identical params (same idempotency key).
        await asyncio.gather(
            *[manager.submit_task("process_payment", params) for _ in range(10)]
        )

        assert enqueue_count == 1, (
            f"Expected exactly 1 enqueue, got {enqueue_count} — "
            "idempotency TOCTOU race condition not fixed"
        )


class TestIdempotencyStoreFailure:
    """Storage failures must surface as IdempotencyStoreError — never as an
    opaque TypeError from treating a truthy Err as a stored record."""

    @pytest.mark.asyncio
    async def test_check_duplicate_raises_idempotency_store_error_on_err(self):
        """An Err from storage raises IdempotencyStoreError, not TypeError."""
        storage = AsyncMock()
        storage.get.return_value = Err(IdempotencyError("connection refused"))
        manager = IdempotencyManager(storage)

        with pytest.raises(IdempotencyStoreError) as excinfo:
            await manager.check_duplicate("key_abc")

        assert "key_abc" in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, IdempotencyError)

    @pytest.mark.asyncio
    async def test_check_duplicate_ok_none_returns_none(self):
        """Ok(None) from storage means no duplicate — returns None."""
        storage = AsyncMock()
        storage.get.return_value = Ok(None)
        manager = IdempotencyManager(storage)

        result = await manager.check_duplicate("key_abc")

        assert result is None

    @pytest.mark.asyncio
    async def test_check_duplicate_ok_record_returns_idempotency_result(self):
        """Ok(record) from storage is returned as an IdempotencyResult."""
        storage = AsyncMock()
        storage.get.return_value = Ok(
            {
                "task_id": "existing_123",
                "idempotency_key": "key_abc",
                "status": "submitted",
                "created_at": "2024-01-01T00:00:00",
                "result": None,
            }
        )
        manager = IdempotencyManager(storage)

        result = await manager.check_duplicate("key_abc")

        assert result is not None
        assert result.task_id == "existing_123"
        assert result.status == "submitted"

    @pytest.mark.asyncio
    async def test_submit_task_fails_closed_on_store_err(self):
        """A failed idempotency lookup aborts submission — it must never
        proceed as if no duplicate exists (which risks duplicate execution)."""
        storage = AsyncMock()
        storage.get.return_value = Err(IdempotencyError("connection refused"))
        queue = AsyncMock()
        idempotency = IdempotencyManager(storage)
        manager = IdempotentTaskManager(queue, idempotency)

        with pytest.raises(IdempotencyStoreError):
            await manager.submit_task(
                "process_payment",
                {"order_id": "123", "amount": 100},
            )

        queue.enqueue.assert_not_called()

    @pytest.mark.asyncio
    async def test_record_completion_raises_on_store_err(self):
        """An Err from storage raises IdempotencyStoreError and never
        overwrites the stored record."""
        storage = AsyncMock()
        storage.get.return_value = Err(IdempotencyError("connection refused"))
        manager = IdempotencyManager(storage)

        with pytest.raises(IdempotencyStoreError):
            await manager.record_completion("key_abc", {"charged": True})

        storage.set.assert_not_called()
