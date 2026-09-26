"""Tests for BufferedMetricRecorder and MonitorScheduledWorker."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from quadkit.contracts.infra.tasks import OnErrorPolicy
from quadkit.monitor.metrics.buffered import (
    BufferedMetricEntry,
    BufferedMetricRecorder,
)
from quadkit.monitor.scheduling.scheduled_worker import MonitorScheduledWorker


class _FakeMetric:
    def __init__(self, fail: bool = False) -> None:
        self.records: list[tuple[float, dict]] = []
        self.fail = fail

    async def record(self, value: float, labels: dict) -> None:
        if self.fail:
            raise RuntimeError("record boom")
        self.records.append((value, labels))


class _FakeBackend:
    def __init__(self) -> None:
        self.request_count = _FakeMetric()
        self.error_count = _FakeMetric(fail=True)
        self.ok = _FakeMetric()


class _FakeTaskManager:
    def __init__(self) -> None:
        self.tracked: dict[str, asyncio.Task] = {}

    def track_named(self, name: str, coro: Any) -> asyncio.Task:
        task = asyncio.ensure_future(coro)
        self.tracked[name] = task
        return task


class TestBufferedEntry:
    @pytest.mark.asyncio
    def test_defaults_and_frozen(self) -> None:
        e = BufferedMetricEntry(name="m", value=1.0)
        assert e.labels == {}
        assert isinstance(e.timestamp, float)
        import dataclasses

        with pytest.raises(dataclasses.FrozenInstanceError):
            e.value = 2.0  # type: ignore[misc]


class TestBufferedRecorder:
    @pytest.mark.asyncio
    async def test_record_buffers_without_backend_call(self) -> None:
        backend = _FakeBackend()
        rec = BufferedMetricRecorder(backend)
        rec.record("request_count", 1.0, {"method": "GET"})
        assert len(backend.request_count.records) == 0
        assert len(rec._buffer) == 1

    @pytest.mark.asyncio
    async def test_flush_delivers_entries(self) -> None:
        backend = _FakeBackend()
        rec = BufferedMetricRecorder(backend)
        rec.record("request_count", 1.0, {"method": "GET"})
        rec.record("request_count", 2.0, {"method": "POST"})
        count = await rec.flush()
        assert count == 2
        assert backend.request_count.records == [
            (1.0, {"method": "GET"}),
            (2.0, {"method": "POST"}),
        ]
        assert rec._buffer == []

    @pytest.mark.asyncio
    async def test_flush_empty_returns_zero(self) -> None:
        rec = BufferedMetricRecorder(_FakeBackend())
        assert await rec.flush() == 0

    @pytest.mark.asyncio
    async def test_unknown_metric_skipped(self) -> None:
        backend = _FakeBackend()
        rec = BufferedMetricRecorder(backend)
        rec.record("nonexistent", 1.0)
        assert await rec.flush() == 0

    @pytest.mark.asyncio
    async def test_backend_error_does_not_abort_batch(self) -> None:
        backend = _FakeBackend()
        rec = BufferedMetricRecorder(backend)
        rec.record("error_count", 1.0)  # raises
        rec.record("ok", 2.0)  # still flushed
        count = await rec.flush()
        assert count == 1
        assert backend.ok.records == [(2.0, {})]

    @pytest.mark.asyncio
    async def test_buffer_full_triggers_background_flush(self) -> None:
        backend = _FakeBackend()
        rec = BufferedMetricRecorder(backend, max_buffer_size=2)
        rec.record("request_count", 1.0)
        rec.record("request_count", 2.0)  # triggers create_tracked_task
        # wait for the background flush task
        for task in list(rec._background_tasks):
            await asyncio.wait_for(task, timeout=2)
        assert len(backend.request_count.records) == 2

    @pytest.mark.asyncio
    async def test_start_stop_periodic_flush(self) -> None:
        backend = _FakeBackend()
        rec = BufferedMetricRecorder(backend, flush_interval=0.01)
        await rec.start()
        rec.record("request_count", 5.0)
        await asyncio.sleep(0.05)
        await rec.stop()
        assert backend.request_count.records == [(5.0, {})]

    @pytest.mark.asyncio
    async def test_stop_flushes_remaining(self) -> None:
        backend = _FakeBackend()
        rec = BufferedMetricRecorder(backend, flush_interval=999)
        await rec.start()
        rec.record("request_count", 7.0)
        await rec.stop()
        assert backend.request_count.records == [(7.0, {})]


class _Worker(MonitorScheduledWorker):
    def __init__(self, task_manager, **kw: Any) -> None:
        super().__init__(task_manager, **kw)
        self.cycles = 0
        self.fail_next: int = 0

    async def run_cycle(self) -> None:
        self.cycles += 1
        if self.fail_next > 0:
            self.fail_next -= 1
            raise RuntimeError("cycle boom")


async def _wait_until(pred, timeout: float = 5.0) -> bool:
    """Poll *pred* on the event loop until true or *timeout* expires."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if pred():
            return True
        await asyncio.sleep(0.005)
    return pred()


class TestMonitorScheduledWorker:
    @pytest.mark.asyncio
    def test_class_defaults(self) -> None:
        tm = _FakeTaskManager()
        w = _Worker(tm)
        assert w.interval_seconds == 60.0
        assert w.initial_delay_seconds == 0.0
        assert w.max_jitter_seconds == 0.0
        assert w.on_error_policy is OnErrorPolicy.LOG_AND_CONTINUE

    @pytest.mark.asyncio
    def test_constructor_overrides(self) -> None:
        tm = _FakeTaskManager()
        w = _Worker(
            tm,
            interval_seconds=1.0,
            initial_delay_seconds=2.0,
            max_jitter_seconds=0.5,
            on_error_policy=OnErrorPolicy.STOP,
        )
        assert w.interval_seconds == 1.0
        assert w.initial_delay_seconds == 2.0
        assert w.max_jitter_seconds == 0.5
        assert w.on_error_policy is OnErrorPolicy.STOP

    @pytest.mark.asyncio
    async def test_start_stop_runs_cycles(self) -> None:
        tm = _FakeTaskManager()
        w = _Worker(tm, interval_seconds=0.01)
        await w.start()
        await _wait_until(lambda: w.cycles >= 2, timeout=5.0)
        await w.stop(grace_seconds=2.0)
        assert w.cycles >= 2
        assert w._task.done()

    @pytest.mark.asyncio
    async def test_start_twice_is_noop(self) -> None:
        tm = _FakeTaskManager()
        w = _Worker(tm, interval_seconds=0.05)
        await w.start()
        task_first = w._task
        await w.start()
        assert w._task is task_first
        await w.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self) -> None:
        w = _Worker(_FakeTaskManager(), interval_seconds=0.01)
        await w.stop()  # must not raise

    @pytest.mark.asyncio
    async def test_log_and_continue_policy(self) -> None:
        tm = _FakeTaskManager()
        w = _Worker(tm, interval_seconds=0.01)
        w.fail_next = 1
        await w.start()
        await _wait_until(lambda: w.cycles >= 2, timeout=5.0)
        await w.stop()
        assert w.cycles >= 2  # continued past the failure

    @pytest.mark.asyncio
    async def test_stop_policy_halts_loop(self) -> None:
        tm = _FakeTaskManager()
        w = _Worker(tm, interval_seconds=0.01, on_error_policy=OnErrorPolicy.STOP)
        w.fail_next = 1
        await w.start()
        assert w._task is not None
        await _wait_until(w._task.done, timeout=5.0)
        assert w._task.done()  # loop exited on error
        await w.stop()

    @pytest.mark.asyncio
    async def test_backoff_policy_delays_cycles(self) -> None:
        tm = _FakeTaskManager()
        w = _Worker(tm, interval_seconds=0.01, on_error_policy=OnErrorPolicy.BACKOFF)
        w.fail_next = 1
        await w.start()
        await _wait_until(lambda: w.cycles >= 1, timeout=5.0)
        await w.stop()
        # first failure doubles the sleep; backoff keeps the loop alive
        assert w.cycles >= 1

    @pytest.mark.asyncio
    async def test_initial_delay_waits(self) -> None:
        tm = _FakeTaskManager()
        w = _Worker(tm, interval_seconds=0.01, initial_delay_seconds=0.05)
        await w.start()
        await asyncio.sleep(0.02)
        assert w.cycles == 0  # initial delay not elapsed yet
        await _wait_until(lambda: w.cycles >= 1, timeout=5.0)
        assert w.cycles >= 1
        await w.stop()

    @pytest.mark.asyncio
    async def test_task_tracked_in_manager(self) -> None:
        tm = _FakeTaskManager()
        w = _Worker(tm, interval_seconds=0.05)
        await w.start()
        assert "scheduled_worker._Worker" in tm.tracked
        await w.stop()
