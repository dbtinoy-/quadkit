"""Tests for concurrency config classes - PoolConfig and ThreadPoolConfig."""

import pytest

from quadkit.concurrency.config import PoolConfig, ThreadPoolConfig
from quadkit.concurrency.config import DispatcherConfig


class TestPoolConfig:
    """Tests for PoolConfig."""

    def test_default_values(self) -> None:
        """Test PoolConfig has correct default values."""
        config = PoolConfig()
        
        assert config.min_size == 1
        assert config.max_size == 10
        assert config.task_queue_size == 100
        assert config.worker_ttl == 3600.0
        assert config.enable_metrics is False

    def test_custom_values(self) -> None:
        """Test PoolConfig accepts custom values."""
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
        """Test PoolConfig validates min_size."""
        with pytest.raises(ValueError):
            PoolConfig(min_size=0)
        
        with pytest.raises(ValueError):
            PoolConfig(min_size=-1)

    def test_validation_max_size(self) -> None:
        """Test PoolConfig validates max_size."""
        with pytest.raises(ValueError):
            PoolConfig(max_size=0)
        
        with pytest.raises(ValueError):
            PoolConfig(max_size=-1)

    def test_validation_task_queue_size(self) -> None:
        """Test PoolConfig validates task_queue_size."""
        with pytest.raises(ValueError):
            PoolConfig(task_queue_size=0)
        
        with pytest.raises(ValueError):
            PoolConfig(task_queue_size=-1)

    def test_validation_worker_ttl(self) -> None:
        """Test PoolConfig validates worker_ttl."""
        config = PoolConfig(worker_ttl=0.0)
        assert config.worker_ttl == 0.0
        
        with pytest.raises(ValueError):
            PoolConfig(worker_ttl=-1.0)


class TestThreadPoolConfig:
    """Tests for ThreadPoolConfig."""

    def test_default_values(self) -> None:
        """Test ThreadPoolConfig has correct default values."""
        config = ThreadPoolConfig()
        
        assert config.max_workers is None
        assert config.thread_name_prefix is None

    def test_custom_values(self) -> None:
        """Test ThreadPoolConfig accepts custom values."""
        config = ThreadPoolConfig(
            max_workers=8,
            thread_name_prefix="worker-",
        )
        
        assert config.max_workers == 8
        assert config.thread_name_prefix == "worker-"

    def test_get_max_workers_with_explicit_value(self) -> None:
        """Test get_max_workers returns explicit value."""
        config = ThreadPoolConfig(max_workers=4)
        
        assert config.get_max_workers() == 4
        assert config.get_max_workers(default=10) == 4

    def test_get_max_workers_with_none_uses_default(self) -> None:
        """Test get_max_workers falls back to default when None."""
        config = ThreadPoolConfig()
        
        assert config.get_max_workers() is None
        assert config.get_max_workers(default=10) == 10

    def test_validation_max_workers(self) -> None:
        """Test ThreadPoolConfig validates max_workers."""
        with pytest.raises(ValueError):
            ThreadPoolConfig(max_workers=0)
        
        with pytest.raises(ValueError):
            ThreadPoolConfig(max_workers=-1)


class TestDispatcherConfig:
    """Tests for DispatcherConfig."""

    def test_default_values(self) -> None:
        """Test DispatcherConfig has correct default values."""
        config = DispatcherConfig()
        
        assert config.max_concurrent_tasks == 100
        assert config.queue_timeout == 30.0
        assert config.retry_failed_tasks is True
        assert config.max_retries == 3
        assert isinstance(config.pool, PoolConfig)
        assert isinstance(config.cpu_pool, ThreadPoolConfig)
        assert isinstance(config.io_pool, ThreadPoolConfig)

    def test_custom_values(self) -> None:
        """Test DispatcherConfig accepts custom values."""
        pool = PoolConfig(min_size=5, max_size=50)
        cpu_pool = ThreadPoolConfig(max_workers=16)
        io_pool = ThreadPoolConfig(max_workers=32)
        
        config = DispatcherConfig(
            max_concurrent_tasks=200,
            queue_timeout=60.0,
            retry_failed_tasks=False,
            max_retries=5,
            pool=pool,
            cpu_pool=cpu_pool,
            io_pool=io_pool,
        )
        
        assert config.max_concurrent_tasks == 200
        assert config.queue_timeout == 60.0
        assert config.retry_failed_tasks is False
        assert config.max_retries == 5
        assert config.pool.min_size == 5
        assert config.cpu_pool.max_workers == 16
        assert config.io_pool.max_workers == 32

    def test_get_cpu_pool_config(self) -> None:
        """Test get_cpu_pool_config returns cpu pool."""
        config = DispatcherConfig()
        cpu_pool = config.get_cpu_pool_config()
        
        assert isinstance(cpu_pool, ThreadPoolConfig)
        assert cpu_pool is config.cpu_pool

    def test_get_io_pool_config(self) -> None:
        """Test get_io_pool_config returns io pool."""
        config = DispatcherConfig()
        io_pool = config.get_io_pool_config()
        
        assert isinstance(io_pool, ThreadPoolConfig)
        assert io_pool is config.io_pool

    def test_validation_max_concurrent_tasks(self) -> None:
        """Test DispatcherConfig validates max_concurrent_tasks."""
        with pytest.raises(ValueError):
            DispatcherConfig(max_concurrent_tasks=0)
        
        with pytest.raises(ValueError):
            DispatcherConfig(max_concurrent_tasks=-1)

    def test_validation_queue_timeout(self) -> None:
        """Test DispatcherConfig validates queue_timeout."""
        config = DispatcherConfig(queue_timeout=0.0)
        assert config.queue_timeout == 0.0
        
        with pytest.raises(ValueError):
            DispatcherConfig(queue_timeout=-1.0)

    def test_validation_max_retries(self) -> None:
        """Test DispatcherConfig validates max_retries."""
        with pytest.raises(ValueError):
            DispatcherConfig(max_retries=-1)
        
        # Zero retries should be valid (no retries)
        config = DispatcherConfig(max_retries=0)
        assert config.max_retries == 0
