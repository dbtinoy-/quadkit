"""Priority + FIFO tests for RedisTaskQueue (unit — mocked Redis client).

The Redis backend encodes priority and insertion order into the ZSET score:

    score = -(priority × PRIORITY_SCALE) + sequence

where ``sequence`` comes from ``INCR {queue}:seq``.  This guarantees:
  - Higher-priority tasks have a *lower* score → dequeued first by ZPOPMIN.
  - Equal-priority tasks are ordered by ascending sequence → FIFO.

These tests exercise the score-computation contract using a mocked Redis client,
so they run without any external infrastructure.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, call

import pytest

from quadkit.tasks.backends.redis import RedisTaskQueue, _PRIORITY_SCALE
from quadkit.tasks.models.job import JobProtocol


def _make_job(job_id: str, priority: int) -> JobProtocol:
    return JobProtocol(id=job_id, name=job_id, priority=priority)


def _build_mock_redis(seq_values: list[int]) -> AsyncMock:
    """Return a mock redis.asyncio.Redis whose incr returns seq_values in order.

    ``pipeline()`` in redis-py is a *synchronous* call that returns an async
    context manager.  We must give it a MagicMock (not AsyncMock) so the call
    itself is not a coroutine, while the context-manager protocol is async.
    """
    from unittest.mock import MagicMock

    mock_redis = AsyncMock()

    # incr: each call resolves to the next value in seq_values
    mock_redis.incr.side_effect = seq_values

    # pipeline() is a sync call; its return value is an async context manager
    mock_pipe = AsyncMock()
    mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
    mock_pipe.__aexit__ = AsyncMock(return_value=None)
    mock_redis.pipeline = MagicMock(return_value=mock_pipe)

    return mock_redis


class TestRedisTaskQueuePriorityScores:
    """Score formula guarantees correct dequeue ordering in the ZSET."""

    @pytest.fixture
    def queue(self) -> RedisTaskQueue:
        """RedisTaskQueue with the real Redis dependency bypassed."""
        q = RedisTaskQueue.__new__(RedisTaskQueue)
        q.redis_url = "redis://localhost"
        q.queue_name = "test_queue"
        q.redis = None  # will be replaced per test
        return q

    # ------------------------------------------------------------------
    # Sequence counter is used
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_enqueue_increments_sequence_key(self, queue: RedisTaskQueue) -> None:
        """enqueue() must call INCR on the sequence key to obtain a FIFO tiebreaker."""
        mock_redis = _build_mock_redis(seq_values=[1])
        queue.redis = mock_redis  # type: ignore[assignment]

        await queue.enqueue(_make_job("j1", priority=5))

        seq_key = f"{queue.queue_name}:seq"
        mock_redis.incr.assert_called_once_with(seq_key)

    @pytest.mark.asyncio
    async def test_each_enqueue_increments_sequence(self, queue: RedisTaskQueue) -> None:
        """Every enqueue() call must call INCR, producing a unique, rising sequence."""
        mock_redis = _build_mock_redis(seq_values=[1, 2, 3])
        queue.redis = mock_redis  # type: ignore[assignment]

        await queue.enqueue(_make_job("j1", priority=5))
        await queue.enqueue(_make_job("j2", priority=5))
        await queue.enqueue(_make_job("j3", priority=5))

        assert mock_redis.incr.call_count == 3

    # ------------------------------------------------------------------
    # Score ordering for priority
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_higher_priority_produces_lower_score(self, queue: RedisTaskQueue) -> None:
        """A higher-priority task must receive a strictly lower ZSET score.

        Lower score → ZPOPMIN returns it first → correct dequeue order.
        """
        mock_redis = _build_mock_redis(seq_values=[1, 2])
        queue.redis = mock_redis  # type: ignore[assignment]

        high_job = _make_job("high", priority=10)
        low_job = _make_job("low", priority=1)

        await queue.enqueue(high_job)
        await queue.enqueue(low_job)

        pipe = mock_redis.pipeline.return_value
        zadd_calls = pipe.zadd.call_args_list
        assert len(zadd_calls) == 2

        # zadd(queue_name, {task_id: score}, nx=True)
        score_high = zadd_calls[0].args[1][high_job.id]
        score_low = zadd_calls[1].args[1][low_job.id]

        assert score_high < score_low, (
            f"High-priority score {score_high} must be < low-priority score {score_low}"
        )

    @pytest.mark.asyncio
    async def test_score_formula_matches_priority_scale(self, queue: RedisTaskQueue) -> None:
        """Score must equal -(priority × _PRIORITY_SCALE) + seq."""
        seq = 7
        priority = 10
        mock_redis = _build_mock_redis(seq_values=[seq])
        queue.redis = mock_redis  # type: ignore[assignment]

        await queue.enqueue(_make_job("j1", priority=priority))

        pipe = mock_redis.pipeline.return_value
        actual_score = pipe.zadd.call_args_list[0].args[1]["j1"]
        expected_score = -(priority * _PRIORITY_SCALE) + seq

        assert actual_score == expected_score, (
            f"Expected score {expected_score}, got {actual_score}"
        )

    # ------------------------------------------------------------------
    # FIFO tiebreaking within same priority
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_same_priority_earlier_enqueue_gets_lower_score(
        self, queue: RedisTaskQueue
    ) -> None:
        """Within the same priority level, the first-enqueued task must have a
        strictly lower score (dequeued first by ZPOPMIN → FIFO)."""
        mock_redis = _build_mock_redis(seq_values=[1, 2])
        queue.redis = mock_redis  # type: ignore[assignment]

        first_job = _make_job("first", priority=5)
        second_job = _make_job("second", priority=5)

        await queue.enqueue(first_job)
        await queue.enqueue(second_job)

        pipe = mock_redis.pipeline.return_value
        zadd_calls = pipe.zadd.call_args_list

        score_first = zadd_calls[0].args[1][first_job.id]
        score_second = zadd_calls[1].args[1][second_job.id]

        assert score_first < score_second, (
            f"First-enqueued score {score_first} must be < second-enqueued score {score_second}"
        )

    @pytest.mark.asyncio
    async def test_same_priority_scores_differ_by_one(self, queue: RedisTaskQueue) -> None:
        """Consecutive same-priority enqueues produce scores that differ by exactly 1
        (seq increments by 1 per call)."""
        mock_redis = _build_mock_redis(seq_values=[3, 4])
        queue.redis = mock_redis  # type: ignore[assignment]

        await queue.enqueue(_make_job("a", priority=5))
        await queue.enqueue(_make_job("b", priority=5))

        pipe = mock_redis.pipeline.return_value
        calls = pipe.zadd.call_args_list
        score_a = calls[0].args[1]["a"]
        score_b = calls[1].args[1]["b"]

        assert score_b - score_a == 1, (
            f"Scores must differ by 1 (got {score_a} and {score_b})"
        )

    # ------------------------------------------------------------------
    # Priority dominates sequence: a lower-priority task enqueued first
    # must never beat a higher-priority task enqueued later.
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_priority_dominates_over_large_sequence(self, queue: RedisTaskQueue) -> None:
        """Even if the low-priority task has a much smaller sequence number,
        the high-priority task must still receive a lower score."""
        # seq=1 for low-priority, seq=10^9 for high-priority — priority must still win
        large_seq = 1_000_000_000
        mock_redis = _build_mock_redis(seq_values=[1, large_seq])
        queue.redis = mock_redis  # type: ignore[assignment]

        low_first = _make_job("low_first", priority=1)
        high_later = _make_job("high_later", priority=10)

        await queue.enqueue(low_first)
        await queue.enqueue(high_later)

        pipe = mock_redis.pipeline.return_value
        calls = pipe.zadd.call_args_list
        score_low = calls[0].args[1][low_first.id]
        score_high = calls[1].args[1][high_later.id]

        assert score_high < score_low, (
            f"High-priority score {score_high} must be < low-priority score {score_low} "
            f"even with seq={large_seq} vs seq=1"
        )

    # ------------------------------------------------------------------
    # nack requeue also uses composite score
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_nack_requeue_uses_composite_score(self, queue: RedisTaskQueue) -> None:
        """nack(requeue=True) must also call INCR and use the composite score,
        placing the task at the back of its priority level."""
        import json
        from unittest.mock import MagicMock

        from quadkit.serialization import dumps  # noqa: F401 – kept for symmetry

        job = _make_job("retried", priority=5)
        task_data_str = json.dumps(job.to_dict())

        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 99  # seq for the nack re-enqueue
        mock_redis.hget.return_value = task_data_str.encode()

        mock_pipe = AsyncMock()
        mock_pipe.__aenter__ = AsyncMock(return_value=mock_pipe)
        mock_pipe.__aexit__ = AsyncMock(return_value=None)
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        queue.redis = mock_redis  # type: ignore[assignment]

        await queue.nack("retried", requeue=True)

        # INCR must have been called for the sequence
        mock_redis.incr.assert_called_once()

        # zadd must use composite score, not bare -priority
        zadd_calls = mock_pipe.zadd.call_args_list
        assert len(zadd_calls) == 1
        score = zadd_calls[0].args[1]["retried"]
        expected_score = -(5 * _PRIORITY_SCALE) + 99
        assert score == expected_score, (
            f"nack requeue score {score} must equal {expected_score}"
        )


class TestRedisClientLifecycle:
    """_get_redis/close must honour the real redis-py driver contract
    (mocks hide sync-vs-async factory semantics)."""

    def test_get_redis_uses_sync_from_url_factory(self) -> None:
        """redis.asyncio.from_url is a sync factory returning the client
        directly — _get_redis must not await it (which raises TypeError
        against the real driver) and must reuse the client afterwards."""
        pytest.importorskip("redis")
        import redis.asyncio as real_redis

        import quadkit.tasks.backends.redis as mod

        sentinel = real_redis.from_url("redis://localhost:6379/0")
        created: list[str] = []

        def fake_from_url(url: str, **_kwargs: object) -> object:
            created.append(url)
            return sentinel

        q = RedisTaskQueue(redis_url="redis://localhost:6379/0", queue_name="t")
        original = mod.redis.from_url
        mod.redis.from_url = fake_from_url
        try:
            client = asyncio.run(q._get_redis())
            assert asyncio.run(q._get_redis()) is sentinel
        finally:
            mod.redis.from_url = original

        assert created == ["redis://localhost:6379/0"]
        assert client is sentinel
        asyncio.run(q.close())
