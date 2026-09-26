"""Tests for tasks config dataclasses."""

import pytest

from quadkit.tasks.config import (
    NamedTaskConfig,
    PostgresTaskConfig,
    TaskBackendConfig,
    TaskConfig,
    TaskSchedulerConfig,
    TaskRateLimitConfig,
    TaskTimeoutConfig,
    TaskWorkerConfig,
)
from quadkit.contracts.core.config import Environment


class TestTaskBackendConfig:
    """Tests for TaskBackendConfig."""

    def test_task_backend_config_defaults(self) -> None:
        """Test TaskBackendConfig default values."""
        config = TaskBackendConfig()
        assert config.type == "memory"
        assert config.queue_name == "tasks"

    def test_task_backend_config_with_redis(self) -> None:
        """Test TaskBackendConfig with Redis."""
        config = TaskBackendConfig(
            type="redis",
            redis_url="redis://localhost:6379",
            queue_name="my-queue",
        )
        assert config.type == "redis"
        assert config.queue_name == "my-queue"


class TestTaskWorkerConfig:
    """Tests for TaskWorkerConfig."""

    def test_task_worker_config_defaults(self) -> None:
        """Test TaskWorkerConfig default values."""
        config = TaskWorkerConfig()
        assert config.worker_count == 1
        assert config.max_concurrent_tasks == 10
        assert config.poll_interval == 0.1
        assert config.shutdown_timeout == 30.0
        assert config.default_timeout == 300.0
        assert config.max_timeout == 3600.0
        assert config.enforce_timeout is True

    def test_task_worker_config_with_values(self) -> None:
        """Test TaskWorkerConfig with custom values."""
        config = TaskWorkerConfig(
            worker_count=4,
            max_concurrent_tasks=20,
            enforce_timeout=False,
        )
        assert config.worker_count == 4
        assert config.max_concurrent_tasks == 20
        assert config.enforce_timeout is False


class TestTaskSchedulerConfig:
    """Tests for TaskSchedulerConfig."""

    def test_task_scheduler_config_defaults(self) -> None:
        """Test TaskSchedulerConfig default values."""
        config = TaskSchedulerConfig()
        assert config.enabled is True
        assert config.check_interval == 1.0
        assert config.timezone == "UTC"

    def test_task_scheduler_config_with_values(self) -> None:
        """Test TaskSchedulerConfig with custom values."""
        config = TaskSchedulerConfig(
            enabled=False,
            check_interval=5.0,
            timezone="America/New_York",
        )
        assert config.enabled is False
        assert config.check_interval == 5.0
        assert config.timezone == "America/New_York"


class TestTaskRateLimitConfig:
    """Tests for TaskRateLimitConfig."""

    def test_task_rate_limit_config_defaults(self) -> None:
        """Test TaskRateLimitConfig default values."""
        config = TaskRateLimitConfig()
        assert config.enabled is False
        assert config.rate == 100
        assert config.per == 1.0
        assert config.burst is None

    def test_task_rate_limit_config_with_values(self) -> None:
        """Test TaskRateLimitConfig with custom values."""
        config = TaskRateLimitConfig(
            enabled=True,
            rate=50,
            per=2.0,
            burst=100,
        )
        assert config.enabled is True
        assert config.rate == 50
        assert config.per == 2.0
        assert config.burst == 100


class TestTaskTimeoutConfig:
    """Tests for TaskTimeoutConfig."""

    def test_task_timeout_config_defaults(self) -> None:
        """Test TaskTimeoutConfig default values."""
        config = TaskTimeoutConfig()
        assert config.default_timeout == 300.0
        assert config.max_timeout == 3600.0

    def test_task_timeout_config_with_values(self) -> None:
        """Test TaskTimeoutConfig with custom values."""
        config = TaskTimeoutConfig(
            default_timeout=60.0,
            max_timeout=600.0,
        )
        assert config.default_timeout == 60.0
        assert config.max_timeout == 600.0


class TestTaskConfig:
    """Tests for the hierarchical TaskConfig."""

    def test_task_config_defaults(self) -> None:
        """Test TaskConfig default values."""
        config = TaskConfig()
        assert config.name == "tasks"
        assert config.enabled is True
        assert config.backend.type == "memory"
        assert config.worker.worker_count == 1
        assert config.scheduler.enabled is True
        assert config.rate_limit.enabled is False
        assert config.timeout.default_timeout == 300.0

    def test_task_config_with_redis_backend(self) -> None:
        """Test TaskConfig with Redis backend."""
        config = TaskConfig(
            backend=TaskBackendConfig(
                type="redis",
                redis_url="redis://localhost:6379",
            ),
        )
        assert config.backend.type == "redis"
        assert config.backend.redis_url.get_secret_value() == "redis://localhost:6379"

    def test_task_config_with_rabbitmq_backend(self) -> None:
        """Test TaskConfig with RabbitMQ backend."""
        config = TaskConfig(
            backend=TaskBackendConfig(
                type="rabbitmq",
                amqp_url="amqp://guest:guest@localhost:5672/",
            ),
        )
        assert config.backend.type == "rabbitmq"
        assert config.backend.amqp_url.get_secret_value() == "amqp://guest:guest@localhost:5672/"

    def test_task_config_with_named_backends(self) -> None:
        """Test TaskConfig with named backends."""
        config = TaskConfig(
            backends=[
                NamedTaskConfig(
                    name="primary",
                    primary=True,
                    type="redis",
                    redis_url="redis://localhost:6379",
                ),
                NamedTaskConfig(
                    name="notifications",
                    type="rabbitmq",
                    amqp_url="amqp://localhost:5672/",
                ),
            ],
        )
        assert len(config.backends) == 2
        assert config.backends[0].name == "primary"
        assert config.backends[0].primary is True
        assert config.backends[1].name == "notifications"

    def test_task_config_validate_production_redis(self) -> None:
        """Test TaskConfig validation for production with placeholder Redis."""
        config = TaskConfig(
            backend=TaskBackendConfig(type="redis"),
        )
        issues = config.validate_for_environment(Environment.PRODUCTION)
        assert len(issues) == 1
        assert issues[0].field == "backend.redis_url"

    def test_task_config_validate_production_amqp(self) -> None:
        """Test TaskConfig validation for production with placeholder AMQP."""
        config = TaskConfig(
            backend=TaskBackendConfig(type="amqp"),
        )
        issues = config.validate_for_environment(Environment.PRODUCTION)
        assert len(issues) == 1
        assert issues[0].field == "backend.amqp_url"

    def test_task_config_validate_production_valid(self) -> None:
        """Test TaskConfig validation passes with valid production config."""
        config = TaskConfig(
            backend=TaskBackendConfig(
                type="redis",
                redis_url="redis://production:6379",
            ),
        )
        issues = config.validate_for_environment(Environment.PRODUCTION)
        assert len(issues) == 0

    def test_task_config_validate_development_passes(self) -> None:
        """Test TaskConfig validation passes in development."""
        config = TaskConfig(
            backend=TaskBackendConfig(type="memory"),
        )
        issues = config.validate_for_environment(Environment.DEVELOPMENT)
        assert len(issues) == 0

    def test_task_config_from_named(self) -> None:
        """Test TaskConfig.from_named creates config from NamedTaskConfig."""
        named = NamedTaskConfig(
            name="my-queue",
            type="redis",
            redis_url="redis://localhost:6379",
            queue_name="custom-queue",
        )
        config = TaskConfig.from_named(named)
        assert config.enabled is True
        assert config.backend.type == "redis"
        assert config.backend.queue_name == "custom-queue"
        assert config.backends == []


class TestWorkerConfig:
    """Tests for WorkerConfig alias (TaskWorkerConfig)."""

    def test_worker_config_is_task_worker_config(self) -> None:
        """Verify WorkerConfig is TaskWorkerConfig."""
        config = TaskWorkerConfig(worker_count=4)
        assert config.worker_count == 4


class TestPostgresTaskConfig:
    """Tests for PostgresTaskConfig."""

    def test_postgres_task_config_defaults(self) -> None:
        """Test PostgresTaskConfig default values."""
        config = PostgresTaskConfig()
        assert config.table == "tasks"
        assert config.pool_min_size == 1
        assert config.pool_max_size == 2
        assert config.command_timeout == 60.0
        assert config.max_attempts == 5

    def test_postgres_task_config_with_values(self) -> None:
        """Test PostgresTaskConfig with custom values."""
        config = PostgresTaskConfig(
            table="custom_tasks",
            pool_min_size=2,
            pool_max_size=10,
            max_attempts=3,
        )
        assert config.table == "custom_tasks"
        assert config.pool_min_size == 2
        assert config.pool_max_size == 10
        assert config.max_attempts == 3
