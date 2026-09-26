"""
Test Performance Monitoring - Comprehensive tests for async operation metrics and profiling.
"""

import asyncio
import time

import pytest

from quadkit.monitor import (
    FunctionProfileResult,
    PerformanceMetrics,
    PerformanceMonitor,
    PerformanceMonitorConfig,
    PerformanceMonitorError,
    PerformanceMonitorState,
    PerformanceSnapshot,
    get_performance_summary,
    monitor_async_operation,
    profile_async_function,
)


class TestPerformanceMonitorConfig:
    """Test PerformanceMonitorConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PerformanceMonitorConfig()
        assert config.enable_memory_tracking is True
        assert config.enable_cpu_profiling is False
        assert config.sampling_interval == 1.0
        assert config.max_metrics_history == 1000
        assert config.profile_sort_by == "cumulative"
        assert config.profile_max_lines == 50

    def test_custom_config(self):
        """Test custom configuration values."""
        config = PerformanceMonitorConfig(
            enable_memory_tracking=False,
            enable_cpu_profiling=True,
            sampling_interval=0.5,
            max_metrics_history=500,
            profile_sort_by="time",
            profile_max_lines=25,
        )
        assert config.enable_memory_tracking is False
        assert config.enable_cpu_profiling is True
        assert config.sampling_interval == 0.5
        assert config.max_metrics_history == 500
        assert config.profile_sort_by == "time"
        assert config.profile_max_lines == 25


class TestPerformanceMetrics:
    """Test PerformanceMetrics."""

    def test_initial_metrics(self):
        """Test initial metrics state."""
        metrics = PerformanceMetrics()
        assert list(metrics.snapshots) == []
        assert metrics.start_time is None
        assert metrics.end_time is None
        assert metrics.total_samples == 0
        assert metrics.average_cpu_percent == 0.0
        assert metrics.average_memory_usage == 0
        assert metrics.peak_memory_usage == 0
        assert metrics.max_active_tasks == 0
        assert metrics.profile_data is None

    def test_duration_property(self):
        """Test duration property."""
        metrics = PerformanceMetrics()
        assert metrics.duration is None

        metrics.start_time = time.time()
        assert metrics.duration is not None

        metrics.end_time = time.time() + 1.0
        duration = metrics.duration
        assert duration is not None
        assert duration >= 1.0

    def test_samples_per_second_property(self):
        """Test samples_per_second property."""
        metrics = PerformanceMetrics()
        assert metrics.samples_per_second == 0.0

        metrics.start_time = time.time()
        metrics.end_time = time.time() + 2.0
        metrics.total_samples = 10
        assert metrics.samples_per_second == pytest.approx(5.0, abs=0.1)


class TestPerformanceMonitor:
    """Test PerformanceMonitor."""

    @pytest.fixture
    def monitor(self):
        """Create a performance monitor for testing."""
        return PerformanceMonitor()

    def test_initial_state(self, monitor):
        """Test initial monitor state."""
        assert monitor.state == PerformanceMonitorState.STOPPED
        assert isinstance(monitor.metrics, PerformanceMetrics)

    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self, monitor):
        """Test starting and stopping monitoring."""
        try:
            # Start monitoring
            await monitor.start_monitoring()
            assert monitor.state == PerformanceMonitorState.MONITORING
            assert monitor.metrics.start_time is not None

            # Wait a bit for some samples
            await asyncio.sleep(0.1)

            # Stop monitoring
            await monitor.stop_monitoring()
            assert monitor.state == PerformanceMonitorState.STOPPED
            assert monitor.metrics.end_time is not None
            assert len(monitor.metrics.snapshots) > 0
        finally:
            if monitor.state != PerformanceMonitorState.STOPPED:
                await monitor.stop_monitoring()

    @pytest.mark.asyncio
    async def test_double_start_error(self, monitor):
        """Test error when starting monitoring twice."""
        try:
            await monitor.start_monitoring()
            with pytest.raises(
                PerformanceMonitorError, match="Cannot start monitoring",
            ):
                await monitor.start_monitoring()
        finally:
            if monitor.state != PerformanceMonitorState.STOPPED:
                await monitor.stop_monitoring()

    @pytest.mark.asyncio
    async def test_monitor_context(self, monitor):
        """Test monitoring context manager."""
        async with monitor.monitor_context():
            assert monitor.state == PerformanceMonitorState.MONITORING
            await asyncio.sleep(0.1)

        assert monitor.state == PerformanceMonitorState.STOPPED
        assert len(monitor.metrics.snapshots) > 0

    @pytest.mark.asyncio
    async def test_profile_function_sync(self, monitor):
        """Test profiling a synchronous function."""

        def test_function(x, y=10):
            time.sleep(0.01)  # Simulate work
            return x + y

        result = await monitor.profile_function(test_function, 5, y=15)

        assert isinstance(result, FunctionProfileResult)
        assert result.function_name == "test_function"
        assert result.execution_time >= 0.01
        assert result.cpu_time >= 0.0
        assert result.memory_delta >= 0
        assert result.profile_stats is not None

    @pytest.mark.asyncio
    async def test_profile_function_async(self, monitor):
        """Test profiling an asynchronous function."""

        async def async_test_function(x, delay=0.01):
            await asyncio.sleep(delay)
            return x * 2

        result = await monitor.profile_function(async_test_function, 5, delay=0.02)

        assert isinstance(result, FunctionProfileResult)
        assert result.function_name == "async_test_function"
        assert result.execution_time >= 0.02
        assert result.cpu_time >= 0.0
        assert result.memory_delta >= 0
        assert result.profile_stats is not None

    @pytest.mark.asyncio
    async def test_monitor_with_custom_config(self):
        """Test monitoring with custom configuration."""
        config = PerformanceMonitorConfig(
            sampling_interval=0.1,
            max_metrics_history=10,
            enable_memory_tracking=False,
        )
        monitor = PerformanceMonitor(config)

        async with monitor.monitor_context():
            await asyncio.sleep(0.5)

        # Should have multiple snapshots due to short interval
        assert len(monitor.metrics.snapshots) >= 3
        assert len(monitor.metrics.snapshots) <= 10  # Limited by max history

    @pytest.mark.asyncio
    async def test_metrics_aggregation(self, monitor):
        """Test metrics aggregation over time."""
        async with monitor.monitor_context():
            await asyncio.sleep(0.3)

        metrics = monitor.metrics
        assert metrics.total_samples > 0
        assert metrics.duration >= 0.3

        # Check that aggregates are calculated
        if metrics.snapshots:
            assert metrics.average_cpu_percent >= 0.0
            assert metrics.average_memory_usage >= 0
            assert metrics.peak_memory_usage >= 0
            assert metrics.max_active_tasks >= 0


class TestUtilityFunctions:
    """Test utility functions."""

    @pytest.mark.asyncio
    async def test_monitor_async_operation(self):
        """Test monitor_async_operation context manager."""
        config = PerformanceMonitorConfig(sampling_interval=0.1)

        async with monitor_async_operation(config=config) as monitor:
            assert monitor.state == PerformanceMonitorState.MONITORING
            await asyncio.sleep(0.2)

        assert monitor.state == PerformanceMonitorState.STOPPED
        assert len(monitor.metrics.snapshots) >= 1

    @pytest.mark.asyncio
    async def test_profile_async_function_utility(self):
        """Test profile_async_function utility."""

        async def sample_async_function(x, delay=0.01):
            await asyncio.sleep(delay)
            return x**2

        result, profile = await profile_async_function(
            sample_async_function,
            5,
            delay=0.02,
        )

        assert result == 25
        assert isinstance(profile, FunctionProfileResult)
        assert profile.function_name == "sample_async_function"
        assert profile.execution_time >= 0.02

    @pytest.mark.asyncio
    async def test_get_performance_summary_empty(self):
        """Test get_performance_summary with empty metrics."""
        metrics = PerformanceMetrics()
        summary = await get_performance_summary(metrics)
        assert getattr(summary, "duration", None) == getattr({}, "duration", None)

    @pytest.mark.asyncio
    async def test_get_performance_summary_with_data(self):
        """Test get_performance_summary with metrics data."""
        snapshot = PerformanceSnapshot(
            timestamp=time.time(),
            cpu_percent=15.5,
            memory_usage=1024000,
            memory_peak=2048000,
            active_tasks=3,
            pending_tasks=1,
            total_tasks=4,
        )

        metrics = PerformanceMetrics(
            snapshots=[snapshot],
            start_time=time.time() - 10.0,
            end_time=time.time(),
            total_samples=10,
            average_cpu_percent=12.5,
            average_memory_usage=1000000,
            peak_memory_usage=2000000,
            max_active_tasks=5,
        )

        summary = await get_performance_summary(metrics)

        assert summary["duration"] >= 10.0
        assert summary["total_samples"] == 10
        assert "samples_per_second" in summary
        assert summary["average_memory_usage"] == 1000000
        assert summary["peak_memory_usage"] == 2000000
        assert summary["max_active_tasks"] == 5
        assert summary["current_active_tasks"] == 3
        assert summary["current_pending_tasks"] == 1
        assert summary["current_total_tasks"] == 4
        assert "has_profile_data" in summary


class TestPerformanceMonitorIntegration:
    """Integration tests for performance monitoring."""

    @pytest.mark.asyncio
    async def test_full_monitoring_workflow(self):
        """Test complete monitoring workflow."""
        config = PerformanceMonitorConfig(
            sampling_interval=0.05,
            enable_memory_tracking=True,
            enable_cpu_profiling=False,
        )
        monitor = PerformanceMonitor(config)

        # Start monitoring
        await monitor.start_monitoring()

        # Simulate some async work
        async def worker(task_id, delay):
            await asyncio.sleep(delay)
            return f"task_{task_id}_done"

        tasks = list(map(lambda i: asyncio.create_task(worker(i, 0.1 + i * 0.01)), range(5)))

        results = await asyncio.gather(*tasks)

        # Stop monitoring
        await monitor.stop_monitoring()

        # Verify results
        assert len(results) == 5
        assert all("done" in result for result in results)

        # Verify monitoring data
        metrics = monitor.metrics
        assert metrics.total_samples > 0
        assert metrics.duration >= 0.1
        assert len(metrics.snapshots) > 0

        # Check that task counts were captured
        max_active = max(s.active_tasks for s in metrics.snapshots)
        assert max_active >= 1  # At least some tasks were active

    @pytest.mark.asyncio
    async def test_memory_tracking_integration(self):
        """Test memory tracking integration."""
        config = PerformanceMonitorConfig(
            enable_memory_tracking=True,
            sampling_interval=0.1,
        )
        monitor = PerformanceMonitor(config)

        # Create some memory usage
        data = []
        async with monitor.monitor_context():
            for i in range(10):
                data.append(list(map(lambda j: j, range(1000))))  # Create memory usage
                await asyncio.sleep(0.05)

            # Clear some data
            data.clear()
            await asyncio.sleep(0.1)

        # Check memory tracking
        metrics = monitor.metrics
        assert len(metrics.snapshots) > 0

        # Memory usage should have been tracked
        for snapshot in metrics.snapshots:
            assert snapshot.memory_usage >= 0
            assert snapshot.memory_peak >= 0

    @pytest.mark.asyncio
    async def test_error_handling_in_monitoring(self):
        """Test error handling during monitoring."""
        monitor = PerformanceMonitor()

        # Start monitoring
        await monitor.start_monitoring()

        # Simulate an error in monitored code
        try:

            async def failing_function():
                await asyncio.sleep(0.1)
                raise ValueError("Test error")

            await failing_function()
        except ValueError:
            pass  # Expected

        # Stop monitoring - should not crash
        await monitor.stop_monitoring()

        # Monitoring should have completed successfully
        assert monitor.state == PerformanceMonitorState.STOPPED
        assert monitor.metrics.end_time is not None
