"""Configuration models for Quadkit Tasks.

This module provides Pydantic models for configuring task
processing, scheduling, and workers.

Example:
    from quadkit.tasks.config import TaskConfig

    # From YAML
    config = TaskConfig.from_yaml("application.yaml")

    # From environment
    config = TaskConfig()  # reads QK_TASKS__* env vars
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from quadkit.config import BaseConfig
from quadkit.contracts.core.config import ConfigIssue, Environment
from quadkit.contracts.infra.resilience.models import RetryConfig
from quadkit.domain.models.base import DomainModel
from quadkit.tasks import constants as tasks_const
from quadkit.validation import ConfigDict, Field, SecretStr


@dataclass(init=False)
class PostgresTaskConfig(DomainModel):
    """Connection configuration for the Postgres task queue backend.

    Note: The dsn field is deprecated. Use provider to inject DatabaseProviderProtocol
    for proper database integration.
    """

    dsn: SecretStr = Field(
        default=SecretStr(""),
        description="Postgres DSN (deprecated - use provider instead)",
    )
    table: str = Field(default="tasks")
    pool_min_size: int = Field(default=1)
    pool_max_size: int = Field(default=2)
    command_timeout: float = Field(default=60.0)
    max_attempts: int = Field(default=5, ge=0)


@dataclass(init=False)
class TaskBackendConfig(BaseConfig):
    """Configuration for task queue backends.

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")"""

    type: str = Field(
        default=tasks_const.DEFAULT_BACKEND, description="Queue backend type"
    )
    redis_url: SecretStr = Field(
        default=SecretStr(tasks_const.DEFAULT_REDIS_URL),
        description="Redis connection URL (may contain credentials).",
    )
    amqp_url: SecretStr = Field(
        default=SecretStr(tasks_const.DEFAULT_AMQP_URL),
        description="AMQP connection URL (may contain credentials).",
    )
    postgres_dsn: SecretStr | None = Field(
        default=None,
        description='Postgres DSN (required when type="postgres"; may contain credentials).',
    )
    queue_name: str = Field(
        default=tasks_const.DEFAULT_QUEUE_NAME, description="Name of the task queue"
    )


@dataclass(init=False)
class TaskWorkerConfig(BaseConfig):
    """Configuration for task workers.

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")"""

    worker_count: int = Field(
        default=tasks_const.DEFAULT_WORKER_COUNT,
        description="Number of worker instances",
    )
    max_concurrent_tasks: int = Field(
        default=tasks_const.DEFAULT_MAX_CONCURRENT_TASKS,
        description="Maximum concurrent tasks per worker",
    )
    poll_interval: float = Field(
        default=tasks_const.DEFAULT_POLL_INTERVAL,
        description="Interval between queue polls (seconds)",
    )
    shutdown_timeout: float = Field(
        default=tasks_const.DEFAULT_SHUTDOWN_TIMEOUT,
        description="Timeout for graceful shutdown (seconds)",
    )
    default_timeout: float = Field(
        default=tasks_const.DEFAULT_TASK_TIMEOUT,
        description="Default timeout for tasks without an explicit timeout (seconds)",
    )
    max_timeout: float = Field(
        default=tasks_const.DEFAULT_MAX_TIMEOUT,
        description="Maximum allowed timeout for any task (seconds)",
    )
    enforce_timeout: bool = Field(
        default=True,
        description="Whether to enforce timeouts on all tasks",
    )


@dataclass(init=False)
class TaskSchedulerConfig(BaseConfig):
    """Configuration for task scheduler.

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")"""

    enabled: bool = Field(default=True, description="Whether scheduling is enabled")
    check_interval: float = Field(
        default=tasks_const.DEFAULT_SCHEDULER_CHECK_INTERVAL,
        description="Interval between schedule checks (seconds)",
    )
    timezone: str = Field(
        default=tasks_const.DEFAULT_SCHEDULER_TIMEZONE,
        description="Timezone for cron expressions",
    )


@dataclass(init=False)
class TaskRateLimitConfig(BaseConfig):
    """Configuration for rate limiting.

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")"""

    enabled: bool = Field(default=False, description="Whether rate limiting is enabled")
    rate: int = Field(
        default=100,
        description="Number of tasks allowed per time period",
    )
    per: float = Field(default=1.0, description="Time period in seconds")
    burst: int | None = Field(default=None, description="Maximum burst size")


@dataclass(init=False)
class TaskTimeoutConfig(BaseConfig):
    """Configuration for task timeout behavior."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    default_timeout: float = Field(
        default=tasks_const.DEFAULT_TASK_TIMEOUT, description="Default timeout"
    )
    max_timeout: float = Field(
        default=tasks_const.DEFAULT_MAX_TIMEOUT, description="Maximum allowed timeout"
    )
    enforce_timeout: bool = Field(default=True, description="Enforce timeouts")


@dataclass(init=False)
class NamedTaskConfig(DomainModel):
    """Configuration for a single named task queue backend.

    Used in TaskConfig.backends to declare multiple task queues
    that the framework registers as Named DI bindings.

    Args:
        name: Unique backend identifier. Used as the Named() DI key.
        primary: Whether this is the primary backend. Primary backends
            also receive the unnamed TaskQueueProtocol binding.
        type: Backend type ('memory', 'redis', 'rabbitmq', 'postgres').
        redis_url: Redis connection URL (when type='redis').
        amqp_url: AMQP connection URL (when type='rabbitmq').
        postgres_dsn: Postgres DSN (when type='postgres').
        queue_name: Queue name for this backend instance.

    Example::
        backends:
          - name: primary
            primary: true
            type: redis
            redis_url: "${REDIS_URL}"
          - name: notifications
            type: rabbitmq
            amqp_url: "${AMQP_URL}"

    Inject by name::
        queue: Annotated[TaskQueueProtocol, Named("notifications")]
    """

    name: str = Field(..., description="Unique backend name for Named DI resolution")
    primary: bool = Field(
        default=False,
        description="Primary backend (also gets unnamed binding)",
    )
    type: str = Field(
        default=tasks_const.DEFAULT_BACKEND,
        description="Backend type: memory, redis, rabbitmq, postgres",
    )
    redis_url: SecretStr | None = Field(
        default=None,
        description="Redis connection URL",
    )
    amqp_url: SecretStr | None = Field(
        default=None,
        description="AMQP connection URL",
    )
    postgres_dsn: SecretStr | None = Field(
        default=None,
        description="Postgres DSN for postgres backend",
    )
    queue_name: str = Field(
        default=tasks_const.DEFAULT_QUEUE_NAME,
        description="Queue name for this backend",
    )


@dataclass(init=False)
class TaskConfig(BaseConfig):
    """Hierarchical root configuration for Quadkit Tasks.

    Attributes:
        name: Configuration name (default: "tasks")
        enabled: Whether tasks module is enabled
        backend: Task queue backend configuration
        worker: Task worker settings
        scheduler: Task scheduler settings
        retry: Task retry configuration
        rate_limit: Task rate limiting
        timeout: Task timeout settings
        extra: Extra configuration
    """

    config_section: ClassVar[str] = "tasks"

    model_config: ClassVar[ConfigDict] = ConfigDict(
        env_prefix=tasks_const.ENV_PREFIX,
        env_nested_delimiter=tasks_const.ENV_NESTED_DELIMITER,
        extra="ignore",
    )  # type: ignore[typeddict-unknown-key]

    name: str = Field(default="tasks", description="Configuration name")
    enabled: bool = Field(default=True, description="Whether tasks module is enabled")
    backend: TaskBackendConfig = Field(
        default_factory=TaskBackendConfig, description="Task queue backend"
    )
    worker: TaskWorkerConfig = Field(default_factory=TaskWorkerConfig)
    scheduler: TaskSchedulerConfig = Field(default_factory=TaskSchedulerConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    rate_limit: TaskRateLimitConfig = Field(default_factory=TaskRateLimitConfig)
    timeout: TaskTimeoutConfig = Field(default_factory=TaskTimeoutConfig)
    extra: dict[str, Any] = Field(default_factory=dict)
    backends: list[NamedTaskConfig] = Field(
        default_factory=list,
        description=(
            "Named task queue backends for multi-queue support. "
            "When non-empty, the provider registers each backend under "
            "Annotated[TaskQueueProtocol, Named(entry.name)]. "
            "The first entry (or the one with primary=True) also receives "
            "the unnamed TaskQueueProtocol binding for backward compatibility."
        ),
    )
    env: Environment | None = Field(default=None, description="Deployment environment")

    def validate_for_environment(
        self, env: Environment | None = None
    ) -> list[ConfigIssue]:
        """Validate task configuration for the given environment.

        Args:
            env: Target environment; resolved from ``self.env`` when ``None``.

        Returns:
            List of :class:`~quadkit.contracts.core.config.ConfigIssue` instances.
        """
        resolved = env or self.env
        issues: list[ConfigIssue] = []
        if resolved == Environment.PRODUCTION:
            placeholder_redis = tasks_const.DEFAULT_REDIS_URL
            placeholder_amqp = tasks_const.DEFAULT_AMQP_URL
            backend_type = self.backend.type
            if (
                backend_type == "redis"
                and self.backend.redis_url.get_secret_value() == placeholder_redis
            ):
                issues.append(
                    ConfigIssue(
                        field="backend.redis_url",
                        message="Redis URL is set to the default placeholder in production.",
                        severity="error",
                        suggestion=(
                            "Set QK_TASKS__BACKEND__REDIS_URL to the production Redis URL."
                        ),
                    )
                )
            if (
                backend_type == "amqp"
                and self.backend.amqp_url.get_secret_value() == placeholder_amqp
            ):
                issues.append(
                    ConfigIssue(
                        field="backend.amqp_url",
                        message="AMQP URL is set to the default placeholder in production.",
                        severity="error",
                        suggestion=(
                            "Set QK_TASKS__BACKEND__AMQP_URL to the production AMQP URL."
                        ),
                    )
                )
        return issues

    @classmethod
    def from_named(cls, entry: NamedTaskConfig) -> TaskConfig:
        """Build a single-backend TaskConfig from a NamedTaskConfig entry.

        Used internally by TasksProvider to create per-backend configs.

        Args:
            entry: The named backend entry to materialise.

        Returns:
            A TaskConfig configured for the single named backend.
        """
        return cls(
            enabled=True,
            backend=TaskBackendConfig(
                type=entry.type,
                redis_url=entry.redis_url or SecretStr(tasks_const.DEFAULT_REDIS_URL),
                amqp_url=entry.amqp_url or SecretStr(tasks_const.DEFAULT_AMQP_URL),
                postgres_dsn=entry.postgres_dsn,
                queue_name=entry.queue_name,
            ),
            backends=[],  # prevent recursion
        )


__all__ = [
    "NamedTaskConfig",
    "PostgresTaskConfig",
    "TaskBackendConfig",
    "TaskConfig",
    "TaskRateLimitConfig",
    "TaskSchedulerConfig",
    "TaskTimeoutConfig",
    "TaskWorkerConfig",
]
