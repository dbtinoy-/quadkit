"""Tests for sse/heartbeat.py — SSEHeartbeatScheduler and get_heartbeat_scheduler."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.web.sse.heartbeat import (
    SSEHeartbeatScheduler,
    _schedulers,
    get_heartbeat_scheduler,
)


class TestSSEHeartbeatSchedulerInit:
    def test_default_values(self) -> None:
        scheduler = SSEHeartbeatScheduler()
        assert scheduler.interval == 30.0
        assert scheduler.tick_resolution == 1.0
        assert scheduler._running is False
        assert scheduler._task is None
        assert scheduler.active_connections == 0

    def test_custom_interval_and_resolution(self) -> None:
        scheduler = SSEHeartbeatScheduler(interval=10.0, tick_resolution=0.5)
        assert scheduler.interval == 10.0
        assert scheduler.tick_resolution == 0.5


class TestSSEHeartbeatSchedulerStartStop:
    @pytest.mark.asyncio
    async def test_start_sets_running_and_creates_task(self) -> None:
        scheduler = SSEHeartbeatScheduler(interval=60.0)
        await scheduler.start()
        try:
            assert scheduler._running is True
            assert scheduler._task is not None
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_start_is_idempotent(self) -> None:
        scheduler = SSEHeartbeatScheduler(interval=60.0)
        await scheduler.start()
        task_first = scheduler._task
        await scheduler.start()  # Should not create new task
        try:
            assert scheduler._task is task_first
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self) -> None:
        scheduler = SSEHeartbeatScheduler(interval=60.0)
        await scheduler.start()
        await scheduler.stop()
        assert scheduler._running is False
        assert scheduler._task is None

    @pytest.mark.asyncio
    async def test_stop_when_not_started_is_noop(self) -> None:
        scheduler = SSEHeartbeatScheduler()
        await scheduler.stop()  # Should not raise


class TestSSEHeartbeatSchedulerRegisterUnregister:
    @pytest.mark.asyncio
    async def test_register_adds_handler(self) -> None:
        scheduler = SSEHeartbeatScheduler(interval=60.0)
        handler = MagicMock()
        await scheduler.register(handler)
        try:
            assert scheduler.active_connections == 1
            assert handler in scheduler._handlers
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_register_starts_scheduler_lazily(self) -> None:
        scheduler = SSEHeartbeatScheduler(interval=60.0)
        handler = MagicMock()
        assert scheduler._running is False
        await scheduler.register(handler)
        try:
            assert scheduler._running is True
        finally:
            await scheduler.stop()

    @pytest.mark.asyncio
    async def test_unregister_removes_handler(self) -> None:
        scheduler = SSEHeartbeatScheduler(interval=60.0)
        handler = MagicMock()
        await scheduler.register(handler)
        await scheduler.unregister(handler)
        assert scheduler.active_connections == 0
        assert handler not in scheduler._handlers
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_unregister_clears_last_sent(self) -> None:
        scheduler = SSEHeartbeatScheduler(interval=60.0)
        handler = MagicMock()
        await scheduler.register(handler)
        handler_id = id(handler)
        assert handler_id in scheduler._last_sent
        await scheduler.unregister(handler)
        assert handler_id not in scheduler._last_sent
        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_is_noop(self) -> None:
        scheduler = SSEHeartbeatScheduler(interval=60.0)
        handler = MagicMock()
        await scheduler.unregister(handler)  # Should not raise

    @pytest.mark.asyncio
    async def test_register_already_running_does_not_restart(self) -> None:
        scheduler = SSEHeartbeatScheduler(interval=60.0)
        await scheduler.start()
        task_before = scheduler._task
        handler = MagicMock()
        await scheduler.register(handler)
        try:
            assert scheduler._task is task_before  # Same task
        finally:
            await scheduler.stop()


class TestSSEHeartbeatSchedulerActiveConnections:
    @pytest.mark.asyncio
    async def test_active_connections_count(self) -> None:
        scheduler = SSEHeartbeatScheduler(interval=60.0)
        h1, h2 = MagicMock(), MagicMock()
        await scheduler.register(h1)
        await scheduler.register(h2)
        try:
            assert scheduler.active_connections == 2
        finally:
            await scheduler.stop()


class TestSSEHeartbeatSchedulerLoop:
    @pytest.mark.asyncio
    async def test_loop_sends_heartbeat_when_interval_elapsed(self) -> None:
        import time

        scheduler = SSEHeartbeatScheduler(interval=0.0, tick_resolution=0.01)
        handler = MagicMock()
        handler.send = AsyncMock()

        # Directly set up the handler without going through register() (which starts the loop)
        async with scheduler._lock:
            scheduler._handlers.add(handler)
            scheduler._last_sent[id(handler)] = time.monotonic() - 100.0

        # Patch sleep so the loop runs once and then stops
        async def mock_sleep(seconds: float) -> None:
            scheduler._running = False

        scheduler._running = True
        with patch("quadkit.web.sse.heartbeat.asyncio.sleep", side_effect=mock_sleep):
            await scheduler._loop()

        handler.send.assert_awaited()

    @pytest.mark.asyncio
    async def test_loop_silently_ignores_send_exception(self) -> None:
        import time

        scheduler = SSEHeartbeatScheduler(interval=0.0, tick_resolution=0.01)
        handler = MagicMock()
        handler.send = AsyncMock(side_effect=RuntimeError("connection closed"))

        async with scheduler._lock:
            scheduler._handlers.add(handler)
            scheduler._last_sent[id(handler)] = time.monotonic() - 100.0

        async def mock_sleep(seconds: float) -> None:
            scheduler._running = False

        scheduler._running = True
        with patch("quadkit.web.sse.heartbeat.asyncio.sleep", side_effect=mock_sleep):
            await scheduler._loop()  # Should not raise


class TestGetHeartbeatScheduler:
    def test_returns_scheduler_instance(self) -> None:
        _schedulers.clear()
        result = get_heartbeat_scheduler(interval=45.0)
        assert isinstance(result, SSEHeartbeatScheduler)
        assert result.interval == 45.0

    def test_caches_by_interval(self) -> None:
        _schedulers.clear()
        first = get_heartbeat_scheduler(interval=20.0)
        second = get_heartbeat_scheduler(interval=20.0)
        assert first is second

    def test_different_intervals_create_separate_schedulers(self) -> None:
        _schedulers.clear()
        s30 = get_heartbeat_scheduler(interval=30.0)
        s60 = get_heartbeat_scheduler(interval=60.0)
        assert s30 is not s60

    def test_default_interval_is_30(self) -> None:
        _schedulers.clear()
        result = get_heartbeat_scheduler()
        assert result.interval == 30.0
