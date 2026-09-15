"""Tests for concurrency configuration modules."""

import pytest

from quadkit.concurrency.config import DispatcherConfig
from quadkit.concurrency.config import PoolConfig, ThreadPoolConfig


class TestPoolConfig:
    """Tests for PoolConfig."""

    def test_default_values(self) -> None:
        """Test PoolConfig with default values."""
        config = PoolConfig()

        assert config.min_size == 1
        assert config.max_size == 10
        assert config.task_queue_size == 100
        assert config.worker_ttl == 3600.0
        assert config.enable_metrics is False

    def test_custom_values(self) -> None:
        """Test PoolConfig with custom values."""
        config = PoolConfig(
            min_size=2,
            max_size=20,
            task_queue_size=200,
            worker_ttl=7200.0,
            enable_metrics=True,
        )

        assert config.min_size == 2
        assert config.max_size == 20
        assert config.task_queue_size == 200
        assert config.worker_ttl == 7200.0
        assert config.enable_metrics is True

    def test_validation_min_size(self) -> None:
        """Test min_size validation."""
        with pytest.raises(ValueError, match="min_size"):
            PoolConfig(min_size=0)

    def test_validation_max_size(self) -> None:
        """Test max_size validation."""
        with pytest.raises(ValueError, match="max_size"):
            PoolConfig(max_size=0)

    def test_validation_task_queue_size(self) -> None:
        """Test task_queue_size validation."""
        with pytest.raises(ValueError, match="task_queue_size"):
            PoolConfig(task_queue_size=0)

    def test_validation_worker_ttl(self) -> None:
        """Test worker_ttl validation."""
        with pytest.raises(ValueError, match="worker_ttl"):
            PoolConfig(worker_ttl=-1)


class TestThreadPoolConfig:
    """Tests for ThreadPoolConfig."""

    def test_default_values(self) -> None:
        """Test ThreadPoolConfig with default values."""
        config = ThreadPoolConfig()

        assert config.max_workers is None
        assert config.thread_name_prefix is None

    def test_custom_values(self) -> None:
        """Test ThreadPoolConfig with custom values."""
        config = ThreadPoolConfig(
            max_workers=8,
            thread_name_prefix="worker-",
        )

        assert config.max_workers == 8
        assert config.thread_name_prefix == "worker-"

    def test_get_max_workers_with_value(self) -> None:
        """Test get_max_workers returns configured value."""
        config = ThreadPoolConfig(max_workers=4)
        assert config.get_max_workers() == 4

    def test_get_max_workers_with_none_uses_default(self) -> None:
        """Test get_max_workers falls back to default."""
        config = ThreadPoolConfig()
        assert config.get_max_workers(default=10) == 10
        assert config.get_max_workers() is None

    def test_validation_max_workers(self) -> None:
        """Test max_workers validation."""
        with pytest.raises(ValueError, match="max_workers"):
            ThreadPoolConfig(max_workers=0)


class TestDispatcherConfig:
    """Tests for DispatcherConfig."""

    def test_default_values(self) -> None:
        """Test DispatcherConfig with default values."""
        config = DispatcherConfig()

        assert config.max_concurrent_tasks == 100
        assert config.queue_timeout == 30.0
        assert config.retry_failed_tasks is True
        assert config.max_retries == 3

    def test_custom_values(self) -> None:
        """Test DispatcherConfig with custom values."""
        config = DispatcherConfig(
            max_concurrent_tasks=50,
            queue_timeout=60.0,
            retry_failed_tasks=False,
            max_retries=5,
        )

        assert config.max_concurrent_tasks == 50
        assert config.queue_timeout == 60.0
        assert config.retry_failed_tasks is False
        assert config.max_retries == 5

    def test_validation_max_concurrent_tasks(self) -> None:
        """Test max_concurrent_tasks validation."""
        with pytest.raises(ValueError, match="max_concurrent_tasks"):
            DispatcherConfig(max_concurrent_tasks=0)

    def test_get_cpu_pool_config(self) -> None:
        """Test get_cpu_pool_config method."""
        config = DispatcherConfig()
        cpu_pool = config.get_cpu_pool_config()
        assert isinstance(cpu_pool, ThreadPoolConfig)

    def test_get_io_pool_config(self) -> None:
        """Test get_io_pool_config method."""
        config = DispatcherConfig()
        io_pool = config.get_io_pool_config()
        assert isinstance(io_pool, ThreadPoolConfig)
