"""Tests for NamedTaskConfig, TaskConfig.backends, and TaskConfig.from_named()."""

from __future__ import annotations

import pytest

from quadkit.tasks.config import NamedTaskConfig, TaskBackendConfig, TaskConfig
from quadkit.tasks import constants as tasks_const
from quadkit.validation import SecretStr


class TestNamedTaskConfigDefaults:
    """Test NamedTaskConfig default field values."""

    def test_name_only_creates_with_defaults(self) -> None:
        """NamedTaskConfig with just name gets correct defaults."""
        cfg = NamedTaskConfig(name="primary")
        assert cfg.name == "primary"
        assert cfg.primary is False
        assert cfg.type == tasks_const.DEFAULT_BACKEND
        assert cfg.redis_url is None
        assert cfg.amqp_url is None
        assert cfg.postgres_dsn is None
        assert cfg.queue_name == tasks_const.DEFAULT_QUEUE_NAME

    def test_primary_flag(self) -> None:
        """NamedTaskConfig with primary=True sets the flag correctly."""
        cfg = NamedTaskConfig(name="main", primary=True)
        assert cfg.primary is True

    def test_redis_backend(self) -> None:
        """NamedTaskConfig with type='redis' and redis_url stores the URL."""
        cfg = NamedTaskConfig(
            name="cache-queue",
            type="redis",
            redis_url=SecretStr("redis://redis-host:6379"),
        )
        assert cfg.type == "redis"
        assert cfg.redis_url is not None
        assert cfg.redis_url.get_secret_value() == "redis://redis-host:6379"

    def test_rabbitmq_backend(self) -> None:
        """NamedTaskConfig with type='rabbitmq' and amqp_url stores the URL."""
        cfg = NamedTaskConfig(
            name="notifications",
            type="rabbitmq",
            amqp_url=SecretStr("amqp://user:pass@broker:5672/"),
        )
        assert cfg.type == "rabbitmq"
        assert cfg.amqp_url is not None
        assert cfg.amqp_url.get_secret_value() == "amqp://user:pass@broker:5672/"

    def test_postgres_backend(self) -> None:
        """NamedTaskConfig with type='postgres' and postgres_dsn stores the DSN."""
        cfg = NamedTaskConfig(
            name="pg-queue",
            type="postgres",
            postgres_dsn=SecretStr("postgresql://user:pass@localhost/tasks"),
        )
        assert cfg.type == "postgres"
        assert cfg.postgres_dsn is not None
        assert cfg.postgres_dsn.get_secret_value() == "postgresql://user:pass@localhost/tasks"


class TestTaskConfigBackends:
    """Test TaskConfig.backends field."""

    def test_backends_defaults_to_empty_list(self) -> None:
        """TaskConfig.backends defaults to []."""
        cfg = TaskConfig()
        assert cfg.backends == []

    def test_backends_accepts_named_entries(self) -> None:
        """TaskConfig accepts a non-empty backends list."""
        entries = [
            NamedTaskConfig(name="primary", primary=True, type="redis"),
            NamedTaskConfig(name="notifications", type="rabbitmq"),
        ]
        cfg = TaskConfig(backends=entries)
        assert len(cfg.backends) == 2
        assert cfg.backends[0].name == "primary"
        assert cfg.backends[1].name == "notifications"


class TestTaskConfigFromNamed:
    """Test TaskConfig.from_named() classmethod."""

    def test_from_named_redis_entry(self) -> None:
        """from_named() with redis entry produces correct backend.type and redis_url."""
        entry = NamedTaskConfig(
            name="primary",
            type="redis",
            redis_url=SecretStr("redis://redis-host:6379"),
        )
        cfg = TaskConfig.from_named(entry)
        assert cfg.enabled is True
        assert cfg.backend.type == "redis"
        assert cfg.backend.redis_url.get_secret_value() == "redis://redis-host:6379"

    def test_from_named_sets_backends_empty(self) -> None:
        """from_named() sets backends=[] to prevent recursion."""
        entry = NamedTaskConfig(name="simple", type="memory")
        cfg = TaskConfig.from_named(entry)
        assert cfg.backends == []

    def test_from_named_uses_default_redis_url_when_none(self) -> None:
        """from_named() falls back to DEFAULT_REDIS_URL when redis_url is None."""
        entry = NamedTaskConfig(name="mem", type="memory")
        cfg = TaskConfig.from_named(entry)
        assert cfg.backend.redis_url.get_secret_value() == tasks_const.DEFAULT_REDIS_URL

    def test_from_named_uses_default_amqp_url_when_none(self) -> None:
        """from_named() falls back to DEFAULT_AMQP_URL when amqp_url is None."""
        entry = NamedTaskConfig(name="mem", type="memory")
        cfg = TaskConfig.from_named(entry)
        assert cfg.backend.amqp_url.get_secret_value() == tasks_const.DEFAULT_AMQP_URL

    def test_from_named_propagates_postgres_dsn(self) -> None:
        """from_named() propagates postgres_dsn into backend."""
        dsn = "postgresql://user:pass@localhost/tasks"
        entry = NamedTaskConfig(
            name="pg",
            type="postgres",
            postgres_dsn=SecretStr(dsn),
        )
        cfg = TaskConfig.from_named(entry)
        assert cfg.backend.postgres_dsn is not None
        assert cfg.backend.postgres_dsn.get_secret_value() == dsn

    def test_from_named_propagates_queue_name(self) -> None:
        """from_named() propagates custom queue_name."""
        entry = NamedTaskConfig(name="custom", type="redis", queue_name="my-queue")
        cfg = TaskConfig.from_named(entry)
        assert cfg.backend.queue_name == "my-queue"


class TestNamedTaskConfigExport:
    """Test that NamedTaskConfig is properly exported from quadkit.tasks."""

    def test_named_task_config_importable_from_package(self) -> None:
        """NamedTaskConfig is accessible via lazy import from quadkit.tasks."""
        import quadkit.tasks as tasks_pkg

        cls = tasks_pkg.NamedTaskConfig
        assert cls is NamedTaskConfig
