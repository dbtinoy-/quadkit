"""Tests for tasks constants."""

import pytest
from quadkit.tasks.constants import (
    ENV_PREFIX,
    ENV_NESTED_DELIMITER,
    DEFAULT_BACKEND,
    DEFAULT_QUEUE_NAME,
    DEFAULT_WORKER_COUNT,
    DEFAULT_MAX_CONCURRENT_TASKS,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_SHUTDOWN_TIMEOUT,
    DEFAULT_TASK_TIMEOUT,
    DEFAULT_MAX_TIMEOUT,
    DEFAULT_SCHEDULER_TIMEZONE,
    DEFAULT_SCHEDULER_CHECK_INTERVAL,
    BACKEND_MEMORY,
    BACKEND_REDIS,
    BACKEND_RABBITMQ,
    BACKEND_POSTGRES,
    DEFAULT_REDIS_URL,
    DEFAULT_AMQP_URL,
)


class TestTasksEnvConstants:
    def test_env_prefix(self) -> None:
        assert ENV_PREFIX == "QK_TASKS__"

    def test_env_nested_delimiter(self) -> None:
        assert ENV_NESTED_DELIMITER == "__"


class TestTasksDefaults:
    def test_default_backend(self) -> None:
        assert DEFAULT_BACKEND == "memory"

    def test_default_queue_name(self) -> None:
        assert DEFAULT_QUEUE_NAME == "tasks"

    def test_default_worker_count(self) -> None:
        assert DEFAULT_WORKER_COUNT == 1

    def test_default_max_concurrent_tasks(self) -> None:
        assert DEFAULT_MAX_CONCURRENT_TASKS == 10

    def test_default_poll_interval(self) -> None:
        assert DEFAULT_POLL_INTERVAL == 0.1

    def test_default_shutdown_timeout(self) -> None:
        assert DEFAULT_SHUTDOWN_TIMEOUT == 30.0

    def test_default_task_timeout(self) -> None:
        assert DEFAULT_TASK_TIMEOUT == 300.0

    def test_default_max_timeout(self) -> None:
        assert DEFAULT_MAX_TIMEOUT == 3600.0

    def test_default_scheduler_timezone(self) -> None:
        assert DEFAULT_SCHEDULER_TIMEZONE == "UTC"

    def test_default_scheduler_check_interval(self) -> None:
        assert DEFAULT_SCHEDULER_CHECK_INTERVAL == 1.0


class TestBackendNames:
    def test_memory(self) -> None:
        assert BACKEND_MEMORY == "memory"

    def test_redis(self) -> None:
        assert BACKEND_REDIS == "redis"

    def test_rabbitmq(self) -> None:
        assert BACKEND_RABBITMQ == "rabbitmq"

    def test_postgres(self) -> None:
        assert BACKEND_POSTGRES == "postgres"


class TestDefaultConnectionStrings:
    def test_redis_url(self) -> None:
        assert DEFAULT_REDIS_URL == "redis://localhost:6379"

    def test_amqp_url(self) -> None:
        assert DEFAULT_AMQP_URL == "amqp://localhost:5672/"
