"""Test enhanced Compute functionality"""

import asyncio
import inspect
import time

import pytest

from quadkit.logging import get_logger

# Import the tasks package first to ensure it's properly initialized
import quadkit.tasks  # noqa: F401
from quadkit.tasks.concurrency.compute import Compute
from quadkit.tasks.types import PoolStrategy

logger = get_logger(__name__)


@pytest.fixture(autouse=True)
def reset_compute():
    """Reset Compute state before each test for isolation."""
    from quadkit.tasks.concurrency.compute import Compute

    Compute.reset()
    Compute.configure(strategy=PoolStrategy.ADAPTIVE, min_workers=1, max_workers=4)
    yield
    Compute.reset()


def cpu_task(x: int) -> int:
    """A CPU-intensive task that can be pickled"""
    result = 0
    for i in range(x):
        result += i * i
    return result


def simple_task(x: int) -> int:
    """Simple task for testing"""
    time.sleep(0.01)
    return x * 2


class TestComputePool:
    """Test Compute pool functionality through the fake executor (no real spawns)."""

    @pytest.mark.asyncio
    async def test_compute_pool_configuration(self, fake_executor):
        """Test pool configuration with ADAPTIVE strategy."""
        Compute.configure(strategy=PoolStrategy.ADAPTIVE, min_workers=1, max_workers=4)
        assert Compute is not None

    @pytest.mark.asyncio
    async def test_simple_task_execution(self, fake_executor):
        """Test execution of simple tasks."""
        Compute.configure(strategy=PoolStrategy.ADAPTIVE, min_workers=1, max_workers=4)
        results = []
        for i in range(3):
            result = await Compute.run(simple_task, i + 1)
            results.append(result)
            assert result == (i + 1) * 2
        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_cpu_intensive_task(self, fake_executor):
        """Test execution of CPU-intensive task."""
        Compute.configure(strategy=PoolStrategy.ADAPTIVE, min_workers=1, max_workers=4)
        cpu_result = await Compute.run(cpu_task, 100)
        expected = 99 * 100 * 199 // 6
        assert cpu_result == expected

    @pytest.mark.asyncio
    async def test_concurrent_task_execution(self, fake_executor):
        """Test multiple concurrent tasks."""
        Compute.configure(strategy=PoolStrategy.ADAPTIVE, min_workers=1, max_workers=4)
        tasks = [Compute.run(simple_task, i) for i in range(5)]
        concurrent_results = await asyncio.gather(*tasks)
        expected_results = [i * 2 for i in range(5)]
        assert concurrent_results == expected_results

    @pytest.mark.asyncio
    async def test_compute_metrics(self, fake_executor):
        """Test that metrics are available after task execution."""
        Compute.configure(strategy=PoolStrategy.ADAPTIVE, min_workers=1, max_workers=4)
        await Compute.run(simple_task, 1)
        await Compute.run(simple_task, 2)
        metrics = Compute.get_metrics()
        if metrics:
            assert metrics.completed_tasks >= 2
            assert isinstance(metrics.completed_tasks, int)
            assert isinstance(metrics.failed_tasks, int)
            assert isinstance(metrics.active_workers, int)

    @pytest.mark.asyncio
    async def test_compute_pool_shutdown(self, fake_executor):
        """Test pool shutdown functionality."""
        Compute.configure(strategy=PoolStrategy.ADAPTIVE, min_workers=1, max_workers=4)
        result = await Compute.run(simple_task, 5)
        assert result == 10
        await Compute.shutdown()
        assert Compute is not None


class TestComputePoolNoGlobalMutation:
    """P2-compute-pool: ComputePool must not mutate the global multiprocessing start method."""

    def test_compute_pool_does_not_mutate_global_mp_context(self) -> None:
        """P2: ComputePool must not call multiprocessing.set_start_method globally."""
        import quadkit.tasks.concurrency.compute as compute_module

        source = inspect.getsource(compute_module)
        assert "set_start_method" not in source, (
            "set_start_method must not be called — use mp.get_context('spawn') instead"
        )
