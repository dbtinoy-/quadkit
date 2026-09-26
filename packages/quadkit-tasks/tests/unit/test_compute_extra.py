"""Focused tests for ComputePool / Compute using a fake executor (no real spawns)."""

from __future__ import annotations

from typing import Any

import pytest

import quadkit.tasks.concurrency.compute as compute_mod
from compute_fakes import ExecutorHolder
from quadkit.tasks.concurrency.compute import (
    Compute,
    ComputePool,
    PoolMetrics,
    ProcessStats,
)
from quadkit.tasks.types import PoolStrategy


def _sum_up_to(x: int) -> int:
    return sum(range(x))


def _always_boom(x: int) -> int:
    raise ValueError("boom")


class FakePool:
    def __init__(self) -> None:
        self.shutdowns = 0
        self.metrics = PoolMetrics(completed_tasks=3)

    async def shutdown(self, wait: bool = True) -> None:
        self.shutdowns += 1

    async def submit(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    def get_metrics(self) -> PoolMetrics:
        return self.metrics


class FakePsutil:
    class NoSuchProcess(Exception):
        pass

    class AccessDenied(Exception):
        pass

    def __init__(self, procs: list[Any]) -> None:
        self._procs = procs
        self.cpu_percent = FakeCpu(cpu=0.0)
        self.virtual_memory = lambda: FakeVirtualMemory(0, 0, 0.0)

    def process_iter(self, attrs: list[str]) -> list[Any]:
        return self._procs


class TestProcessStats:
    def test_defaults(self) -> None:
        s = ProcessStats(pid=1)
        assert s.tasks_completed == 0
        assert s.tasks_failed == 0
        assert s.cpu_percent == 0.0
        assert s.memory_mb == 0.0
        assert s.is_healthy is True
        assert s.last_active > 0


class TestPoolInit:
    def test_memory_limit_explicit(self, fake_executor: ExecutorHolder) -> None:
        pool = ComputePool(strategy=PoolStrategy.FIXED, memory_limit_mb=512)
        assert pool.memory_limit_mb == 512
        import asyncio
        asyncio.run(pool.shutdown())

    def test_memory_limit_fallback(self, fake_executor: ExecutorHolder) -> None:
        pool = ComputePool(strategy=PoolStrategy.FIXED)
        assert pool.memory_limit_mb == 1024
        import asyncio
        asyncio.run(pool.shutdown())

    def test_max_workers_default(self, fake_executor: ExecutorHolder) -> None:
        pool = ComputePool(strategy=PoolStrategy.FIXED)
        assert pool.max_workers == 8  # cpu_count(4) * 2
        import asyncio
        asyncio.run(pool.shutdown())

    def test_executor_created_on_init(self, fake_executor: ExecutorHolder) -> None:
        pool = ComputePool(strategy=PoolStrategy.FIXED)
        assert pool._executor is not None
        assert pool._monitor_thread is not None
        import asyncio
        asyncio.run(pool.shutdown())


class TestTargetWorkers:
    def test_fixed(self, fake_executor: ExecutorHolder) -> None:
        pool = ComputePool(strategy=PoolStrategy.FIXED, min_workers=2, max_workers=3)
        assert pool._calculate_target_workers() == 3
        import asyncio
        asyncio.run(pool.shutdown())

    def test_fixed_cpu_capped(self, fake_executor: ExecutorHolder) -> None:
        pool = ComputePool(strategy=PoolStrategy.FIXED, min_workers=2, max_workers=10)
        assert pool._calculate_target_workers() == 4
        import asyncio
        asyncio.run(pool.shutdown())

    def test_dynamic_without_psutil(self, fake_executor: ExecutorHolder) -> None:
        pool = ComputePool(strategy=PoolStrategy.DYNAMIC, min_workers=1, max_workers=10)
        assert pool._calculate_target_workers() == 4
        import asyncio
        asyncio.run(pool.shutdown())

    def test_adaptive_without_psutil(self, fake_executor: ExecutorHolder) -> None:
        pool = ComputePool(strategy=PoolStrategy.ADAPTIVE, min_workers=1, max_workers=10)
        assert pool._calculate_target_workers() == 4
        import asyncio
        asyncio.run(pool.shutdown())

    def test_adaptive_min_workers_respected(
        self, fake_executor: ExecutorHolder
    ) -> None:
        pool = ComputePool(strategy=PoolStrategy.ADAPTIVE, min_workers=3, max_workers=2)
        assert pool._calculate_target_workers() == 3
        import asyncio
        asyncio.run(pool.shutdown())


class FakeCpu(dict):
    def __call__(self, interval: float = 0.0) -> float:
        return self["cpu"]

    cpu_percent = None  # attribute exists in psutil module too


class FakeVirtualMemory:
    def __init__(self, total: int, available: int, percent: float) -> None:
        self.total = total
        self.available = available
        self.percent = percent


class TestTargetWorkersWithPsutil:
    def test_dynamic_high_load(
        self, fake_executor: ExecutorHolder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        psutil = FakePsutil([])
        psutil.cpu_percent = FakeCpu(cpu=95.0)
        psutil.virtual_memory = lambda: FakeVirtualMemory(0, 0, 90.0)
        monkeypatch.setattr(compute_mod, "HAS_PSUTIL", True)
        monkeypatch.setattr(compute_mod, "psutil", psutil)
        pool = ComputePool(strategy=PoolStrategy.DYNAMIC, min_workers=1, max_workers=10)
        assert pool._calculate_target_workers() == 1
        import asyncio
        asyncio.run(pool.shutdown())

    def test_dynamic_low_load(
        self, fake_executor: ExecutorHolder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        psutil = FakePsutil([])
        psutil.cpu_percent = FakeCpu(cpu=5.0)
        psutil.virtual_memory = lambda: FakeVirtualMemory(0, 0, 20.0)
        monkeypatch.setattr(compute_mod, "HAS_PSUTIL", True)
        monkeypatch.setattr(compute_mod, "psutil", psutil)
        pool = ComputePool(strategy=PoolStrategy.DYNAMIC, min_workers=1, max_workers=20)
        assert pool._calculate_target_workers() == 8  # cpu_count * 2
        import asyncio
        asyncio.run(pool.shutdown())

    def test_adaptive_low_load(
        self, fake_executor: ExecutorHolder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        psutil = FakePsutil([])
        psutil.cpu_percent = FakeCpu(cpu=10.0)
        psutil.virtual_memory = lambda: FakeVirtualMemory(0, 8 * 1024**3, 10.0)
        monkeypatch.setattr(compute_mod, "HAS_PSUTIL", True)
        monkeypatch.setattr(compute_mod, "psutil", psutil)
        pool = ComputePool(strategy=PoolStrategy.ADAPTIVE)
        # cpu=4, mem 8GB -> min(4, 16) = 4; no cpu throttling
        assert pool._calculate_target_workers() == 4
        import asyncio
        asyncio.run(pool.shutdown())

    def test_adaptive_high_cpu_halves_workers(
        self, fake_executor: ExecutorHolder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        psutil = FakePsutil([])
        psutil.cpu_percent = FakeCpu(cpu=85.0)
        psutil.virtual_memory = lambda: FakeVirtualMemory(0, 4 * 1024**3, 10.0)
        monkeypatch.setattr(compute_mod, "HAS_PSUTIL", True)
        monkeypatch.setattr(compute_mod, "psutil", psutil)
        pool = ComputePool(strategy=PoolStrategy.ADAPTIVE)
        # cpu=4, mem 4GB -> min(4, 8) = 4; 85 > 60 -> max(1, 2) = 2
        assert pool._calculate_target_workers() == 2
        import asyncio
        asyncio.run(pool.shutdown())

    def test_memory_limit_from_psutil(
        self, fake_executor: ExecutorHolder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        psutil = FakePsutil([])
        psutil.virtual_memory = lambda: FakeVirtualMemory(8 * 1024**3, 0, 0.0)
        monkeypatch.setattr(compute_mod, "HAS_PSUTIL", True)
        monkeypatch.setattr(compute_mod, "psutil", psutil)
        pool = ComputePool(strategy=PoolStrategy.FIXED)
        assert pool.memory_limit_mb == 8 * 1024 // 4
        import asyncio
        asyncio.run(pool.shutdown())

    def test_unknown_strategy_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        class FakeStrategy:
            FIXED = PoolStrategy.FIXED
            DYNAMIC = PoolStrategy.DYNAMIC
            ADAPTIVE = PoolStrategy.ADAPTIVE
            MYSTERY = "mystery"

        pool = ComputePool(strategy=PoolStrategy.FIXED)
        pool.strategy = FakeStrategy.MYSTERY  # type: ignore[assignment]
        with pytest.raises(AssertionError):
            pool._calculate_target_workers()
        import asyncio
        asyncio.run(pool.shutdown())


class TestWorkerManagement:
    def test_update_worker_stats_without_psutil(
        self, fake_executor: ExecutorHolder
    ) -> None:
        pool = ComputePool(strategy=PoolStrategy.FIXED)
        pool._workers = {1: ProcessStats(pid=1)}
        pool._update_worker_stats()
        assert pool._workers[1].is_healthy is True
        import asyncio
        asyncio.run(pool.shutdown())

    def test_worker_stats_with_psutil(
        self, fake_executor: ExecutorHolder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class Proc:
            def __init__(self, pid: int, cpu: float | None, rss: int) -> None:
                self.info = {
                    "pid": pid,
                    "cpu_percent": cpu,
                    "memory_info": type("MI", (), {"rss": rss})(),
                }

        procs = [Proc(1, 12.5, 2 * 1024 * 1024), Proc(2, None, 0)]
        psutil = FakePsutil(procs)
        monkeypatch.setattr(compute_mod, "HAS_PSUTIL", True)
        monkeypatch.setattr(compute_mod, "psutil", psutil)
        pool = ComputePool(strategy=PoolStrategy.FIXED)
        pool._workers = {
            1: ProcessStats(pid=1),
            2: ProcessStats(pid=2),
            3: ProcessStats(pid=3),
        }
        pool._update_worker_stats()
        assert pool._workers[1].cpu_percent == 12.5
        assert pool._workers[1].memory_mb == 2
        assert pool._workers[2].cpu_percent == 0.0
        assert pool._workers[2].is_healthy is True
        assert pool._workers[3].is_healthy is False  # missing from process list
        import asyncio
        asyncio.run(pool.shutdown())

    def test_worker_stats_ignores_vanished_proc(
        self, fake_executor: ExecutorHolder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class Gone:
            @property
            def info(self) -> dict:
                raise FakePsutil.NoSuchProcess(999)

        psutil = FakePsutil([Gone()])
        monkeypatch.setattr(compute_mod, "HAS_PSUTIL", True)
        monkeypatch.setattr(compute_mod, "psutil", psutil)
        pool = ComputePool(strategy=PoolStrategy.FIXED)
        pool._workers = {999: ProcessStats(pid=999)}
        pool._update_worker_stats()
        assert pool._workers[999].is_healthy is False
        import asyncio
        asyncio.run(pool.shutdown())

    def test_check_worker_health_evicts_unhealthy(
        self, fake_executor: ExecutorHolder
    ) -> None:
        pool = ComputePool(strategy=PoolStrategy.FIXED)
        pool._workers = {
            1: ProcessStats(pid=1, is_healthy=True),
            2: ProcessStats(pid=2, is_healthy=False),
        }
        pool._check_worker_health()
        assert list(pool._workers) == [1]
        import asyncio
        asyncio.run(pool.shutdown())

    def test_adjust_pool_size_noop_for_fixed(
        self, fake_executor: ExecutorHolder
    ) -> None:
        pool = ComputePool(strategy=PoolStrategy.FIXED)
        pool._workers = {1: ProcessStats(pid=1)}
        pool._adjust_pool_size()  # should not raise
        import asyncio
        asyncio.run(pool.shutdown())

    def test_adjust_pool_size_targets(self, fake_executor: ExecutorHolder) -> None:
        pool = ComputePool(strategy=PoolStrategy.DYNAMIC)
        pool._workers = {
            1: ProcessStats(pid=1),
            2: ProcessStats(pid=2),
            3: ProcessStats(pid=3, is_healthy=False),
        }
        pool._adjust_pool_size()
        import asyncio
        asyncio.run(pool.shutdown())

    def test_update_metrics(self, fake_executor: ExecutorHolder) -> None:
        pool = ComputePool(strategy=PoolStrategy.FIXED)
        pool._workers = {
            1: ProcessStats(pid=1, cpu_percent=10.0, memory_mb=5.0),
            2: ProcessStats(pid=2, cpu_percent=20.0, memory_mb=15.0, is_healthy=False),
        }
        pool._task_durations = [1.0, 3.0]
        pool._update_metrics()
        assert pool._metrics.active_workers == 1
        assert pool._metrics.total_workers == 2
        assert pool._metrics.pool_cpu_percent == 10.0
        assert pool._metrics.pool_memory_mb == 5.0
        assert pool._metrics.avg_task_duration == 2.0
        import asyncio
        asyncio.run(pool.shutdown())


class TestSubmit:
    @pytest.mark.asyncio
    async def test_submit_success(self, fake_executor: ExecutorHolder) -> None:
        pool = ComputePool(strategy=PoolStrategy.FIXED)
        result = await pool.submit(_sum_up_to, 5)
        assert result == 10
        assert pool._metrics.completed_tasks == 1
        await pool.shutdown()

    @pytest.mark.asyncio
    async def test_submit_failure_counts_and_reraises(
        self, fake_executor: ExecutorHolder
    ) -> None:
        pool = ComputePool(strategy=PoolStrategy.FIXED)
        with pytest.raises(ValueError, match="boom"):
            await pool.submit(_always_boom, 1)
        assert pool._metrics.failed_tasks == 1
        await pool.shutdown()

    @pytest.mark.asyncio
    async def test_duration_buffer_capped(self, fake_executor: ExecutorHolder) -> None:
        pool = ComputePool(strategy=PoolStrategy.FIXED)
        pool._task_durations = [0.0] * 1000
        await pool.submit(_sum_up_to, 1)
        assert len(pool._task_durations) <= 1000
        await pool.shutdown()

    @pytest.mark.asyncio
    async def test_get_metrics_returns_copy(
        self, fake_executor: ExecutorHolder
    ) -> None:
        pool = ComputePool(strategy=PoolStrategy.FIXED)
        metrics = pool.get_metrics()
        assert metrics.total_workers == 0
        metrics.total_workers = 99
        assert pool._metrics.total_workers == 0
        await pool.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown(self, fake_executor: ExecutorHolder) -> None:
        pool = ComputePool(strategy=PoolStrategy.FIXED)
        await pool.shutdown()
        assert fake_executor.executor is not None
        assert fake_executor.executor.shutdown_called is True
        assert pool._executor is None
        assert pool._workers == {}


class TestComputeClass:
    @pytest.mark.asyncio
    async def test_reset_without_pool(self) -> None:
        Compute._pool = None
        Compute.reset()
        assert Compute._pool is None
        assert Compute._test_mode is False

    @pytest.mark.asyncio
    async def test_reset_with_pool_in_running_loop(self) -> None:
        Compute._pool = FakePool()  # type: ignore[assignment]
        Compute.reset()
        assert Compute._pool is None

    def test_enter_exit_test_mode(self) -> None:
        Compute._pool = FakePool()  # type: ignore[assignment]
        Compute.enter_test_mode()
        assert Compute._test_mode is True
        assert Compute._pool is None
        Compute.exit_test_mode()
        assert Compute._test_mode is False
        assert isinstance(Compute._pool, FakePool)

    def test_exit_test_mode_when_not_active(self) -> None:
        Compute._test_mode = False
        Compute._pool = None
        Compute.exit_test_mode()
        assert Compute._pool is None

    @pytest.mark.asyncio
    async def test_run_autoconfigures(self, fake_executor: ExecutorHolder) -> None:
        Compute._pool = None
        result = await Compute.run(_sum_up_to, 4)
        assert result == 6
        assert Compute._pool is not None
        await Compute.shutdown()

    def test_get_metrics_without_pool(self) -> None:
        Compute._pool = None
        assert Compute.get_metrics() is None

    @pytest.mark.asyncio
    async def test_get_metrics_with_pool(self) -> None:
        Compute._pool = FakePool()  # type: ignore[assignment]
        metrics = Compute.get_metrics()
        assert metrics is not None
        assert metrics.completed_tasks == 3

    @pytest.mark.asyncio
    async def test_shutdown_with_pool(self) -> None:
        pool = FakePool()
        Compute._pool = pool  # type: ignore[assignment]
        await Compute.shutdown()
        assert pool.shutdowns == 1
        assert Compute._pool is None

    @pytest.mark.asyncio
    async def test_configure_replaces_pool(self, fake_executor: ExecutorHolder) -> None:
        old = FakePool()
        Compute._pool = old  # type: ignore[assignment]
        Compute.configure(strategy=PoolStrategy.FIXED, max_workers=2)
        assert isinstance(Compute._pool, ComputePool)
        assert Compute._pool.max_workers == 2
        await Compute.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_waits_for_monitor_thread(
        self, fake_executor: ExecutorHolder
    ) -> None:
        pool = ComputePool(strategy=PoolStrategy.FIXED)
        await pool.shutdown()
        assert pool._monitor_thread is not None
        assert not pool._monitor_thread.is_alive()