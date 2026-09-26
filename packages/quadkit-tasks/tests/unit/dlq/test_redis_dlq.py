"""Tests for RedisDLQBackend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.tasks.dlq.redis_dlq import RedisDLQBackend


@dataclass
class _FakeJob:
    """Minimal fake job for DLQ tests."""

    id: str
    queue: str
    payload: dict[str, Any]
    retry_count: int = 0


class TestRedisDLQBackend:
    """Unit tests for RedisDLQBackend."""

    @pytest.fixture
    def mock_redis(self) -> MagicMock:
        """Return a mock async Redis client."""
        redis = MagicMock()
        pipe = MagicMock()
        pipe.lpush = MagicMock()
        pipe.ltrim = MagicMock()
        pipe.execute = AsyncMock(return_value=[1, 1])
        redis.pipeline = MagicMock(return_value=pipe)
        redis.lrange = AsyncMock(return_value=[])
        redis.llen = AsyncMock(return_value=0)
        return redis

    @pytest.fixture
    def dlq(self, mock_redis: MagicMock) -> RedisDLQBackend:
        """Return a RedisDLQBackend backed by a mock Redis client."""
        return RedisDLQBackend(redis=mock_redis, queue_name="test", max_entries=1000)

    @pytest.mark.asyncio
    async def test_push_stores_entry(self, dlq: RedisDLQBackend, mock_redis: MagicMock) -> None:
        """push() should serialize the job and call lpush + ltrim atomically."""
        job = _FakeJob(id="job-1", queue="emails", payload={"to": "a@b.com"})

        await dlq.push(job, error="Connection refused")

        pipe = mock_redis.pipeline.return_value
        pipe.lpush.assert_called_once()
        pipe.ltrim.assert_called_once()
        pipe.execute.assert_awaited_once()

        # Verify key namespacing
        key_arg = pipe.lpush.call_args[0][0]
        assert "test" in key_arg

    @pytest.mark.asyncio
    async def test_push_includes_error_and_metadata(
        self, dlq: RedisDLQBackend, mock_redis: MagicMock
    ) -> None:
        """push() serialized entry must contain job_id, error, and failed_at."""
        from quadkit.serialization import loads_str

        job = _FakeJob(id="job-99", queue="tasks", payload={})

        await dlq.push(job, error="timeout")

        pipe = mock_redis.pipeline.return_value
        raw = pipe.lpush.call_args[0][1]
        entry = loads_str(raw)

        assert entry["job_id"] == "job-99"
        assert entry["error"] == "timeout"
        assert "failed_at" in entry

    @pytest.mark.asyncio
    async def test_list_entries_decodes_json(
        self, dlq: RedisDLQBackend, mock_redis: MagicMock
    ) -> None:
        """list_entries() should decode serialized entries from Redis."""
        from quadkit.serialization import dumps_str

        raw_entry = dumps_str({"job_id": "x", "error": "err", "failed_at": "2024-01-01T00:00:00"})
        mock_redis.lrange = AsyncMock(return_value=[raw_entry])

        entries = await dlq.list_entries(limit=10)

        assert len(entries) == 1
        assert entries[0]["job_id"] == "x"
        mock_redis.lrange.assert_awaited_once_with(dlq._key, 0, 9)

    @pytest.mark.asyncio
    async def test_size_returns_llen(
        self, dlq: RedisDLQBackend, mock_redis: MagicMock
    ) -> None:
        """size() should delegate to Redis llen."""
        mock_redis.llen = AsyncMock(return_value=42)

        result = await dlq.size()

        assert result == 42
        mock_redis.llen.assert_awaited_once_with(dlq._key)

    @pytest.mark.asyncio
    async def test_max_entries_respected(
        self, mock_redis: MagicMock
    ) -> None:
        """ltrim should use max_entries - 1 as the upper bound."""
        dlq = RedisDLQBackend(redis=mock_redis, queue_name="q", max_entries=500)
        job = _FakeJob(id="j1", queue="q", payload={})

        await dlq.push(job, error="oops")

        pipe = mock_redis.pipeline.return_value
        ltrim_args = pipe.ltrim.call_args[0]
        # ltrim(key, 0, max_entries - 1)
        assert ltrim_args[2] == 499
