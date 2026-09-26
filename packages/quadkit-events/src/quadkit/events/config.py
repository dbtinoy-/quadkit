"""Consolidated Events configuration.

This file combines all 9 config submodule files into a single module.
Replaces the need for the separate config/ directory by eliminating
TYPE_CHECKING guards and cast() wrappers that prevented runtime type resolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config.base import BaseConfig
from quadkit.contracts.core.config import Environment
from quadkit.events import constants as const
from quadkit.events.stores.postgres.config import PostgresEventStoreConfig
from quadkit.events.types import EventStoreBackend, SnapshotStrategy
from quadkit.validation import ConfigDict, Field, SecretStr, field_validator

# ─────────────────────────────────────────────────────────────────────
# Bus Configurations
# ─────────────────────────────────────────────────────────────────────


@dataclass(init=False)
class CommandBusConfig(BaseConfig):
    """Configuration for command bus."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    max_retries: int = Field(3, ge=0)
    retry_delay_seconds: float = Field(1.0, ge=0.1)
    timeout_seconds: float = Field(30.0, ge=1.0)
    enable_validation: bool = Field(True)
    enable_logging: bool = Field(True)
    enable_metrics: bool = Field(True)


@dataclass(init=False)
class QueryBusConfig(BaseConfig):
    """Configuration for query bus."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    timeout_seconds: float = Field(30.0, ge=1.0)
    enable_logging: bool = Field(True)
    enable_metrics: bool = Field(True)


@dataclass(init=False)
class EventBusConfig(BaseConfig):
    """Configuration for event bus."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    max_concurrent_handlers: int = Field(10, ge=1)
    handler_timeout_seconds: float = Field(30.0, ge=1.0)
    retry_failed_handlers: bool = Field(True)
    max_handler_retries: int = Field(3, ge=0)
    enable_dead_letter: bool = Field(True)
    allow_no_handlers: bool = Field(True)
    parallel_dispatch: bool = Field(True)
    continue_on_error: bool = Field(True)
    max_queue_per_subscriber: int = Field(
        1000,
        ge=0,
        description=(
            "Maximum number of events queued per event type before backpressure "
            "is applied. 0 means unbounded (no backpressure)."
        ),
    )


# ─────────────────────────────────────────────────────────────────────
# Event Store Configurations
# ─────────────────────────────────────────────────────────────────────


@dataclass(init=False)
class InMemoryEventStoreConfig(BaseConfig):
    """Configuration for in-memory event store."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    max_events_per_stream: int = Field(10000, ge=100)
    enable_snapshots: bool = Field(True)


@dataclass(init=False)
class MongoDBEventStoreConfig(BaseConfig):
    """Configuration for MongoDB event store (top-level user config).

    Used by :attr:`EventsConfig.mongodb <quadkit.events.config.EventsConfig.mongodb>`.
    For the store-level connection config used by :class:`~quadkit.events.stores.MongoDBSnapshotStore`,
    see :class:`quadkit.events.stores.mongodb.MongoDBConfig`.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    connection_string: SecretStr = Field(..., description="MongoDB connection string")
    database_name: str = Field("events")
    events_collection: str = Field("domain_events")
    snapshots_collection: str = Field("snapshots")
    max_pool_size: int = Field(10, ge=1)
    server_selection_timeout: int = Field(30000)

    @field_validator("connection_string")
    @classmethod
    def validate_connection_string(cls, v: SecretStr | str) -> SecretStr:
        """Validate and coerce MongoDB connection string to SecretStr."""
        raw = v.get_secret_value() if isinstance(v, SecretStr) else v
        if not raw.startswith("mongodb://") and not raw.startswith("mongodb+srv://"):
            raise ValueError(
                "Connection string must start with mongodb:// or mongodb+srv://"
            )
        return SecretStr(raw) if isinstance(v, str) else v


@dataclass(init=False)
class SqliteConfig(BaseConfig):
    """SQLite configuration for event stores.

    Table-name and DDL fields mirror :class:`~quadkit.events.stores.postgres.PostgresEventStoreConfig`
    so both SQL backends behave identically under default configuration.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    database: str = Field(default="./events.db")
    pragmas: dict[str, str] = Field(default_factory=dict)
    wal_mode: bool = Field(default=True)
    journal_mode: str = Field(default="WAL")
    events_table: str = Field(default="events")
    snapshots_table: str = Field(default="snapshots")
    auto_create_tables: bool = Field(default=True)


# ─────────────────────────────────────────────────────────────────────
# Middleware Configurations
# ─────────────────────────────────────────────────────────────────────


@dataclass(init=False)
class LoggingMiddlewareConfig(BaseConfig):
    """Configuration for logging middleware."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    enabled: bool = Field(True)
    log_level: str = Field("INFO")
    include_payload: bool = Field(False)
    max_payload_length: int = Field(1000, ge=100)


@dataclass(init=False)
class ValidationMiddlewareConfig(BaseConfig):
    """Configuration for validation middleware."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    enabled: bool = Field(True)
    strict_mode: bool = Field(True)


@dataclass(init=False)
class TransactionMiddlewareConfig(BaseConfig):
    """Configuration for transaction middleware."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    enabled: bool = Field(True)
    isolation_level: str = Field("READ_COMMITTED")
    timeout_seconds: float = Field(30.0, ge=1.0)


@dataclass(init=False)
class RetryMiddlewareConfig(BaseConfig):
    """Configuration for retry middleware."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    enabled: bool = Field(True)
    max_retries: int = Field(3, ge=0)
    initial_delay_seconds: float = Field(0.1, ge=0.01)
    max_delay_seconds: float = Field(10.0, ge=1.0)
    exponential_base: float = Field(2.0, ge=1.1)


@dataclass(init=False)
class MetricsMiddlewareConfig(BaseConfig):
    """Configuration for metrics middleware."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    enabled: bool = Field(True)
    prefix: str = Field("events")
    include_histograms: bool = Field(True)
    histogram_buckets: list[float] = Field(
        default_factory=lambda: [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
    )


# ─────────────────────────────────────────────────────────────────────
# Pattern Configurations
# ─────────────────────────────────────────────────────────────────────


@dataclass(init=False)
class ProjectionConfig(BaseConfig):
    """Configuration for event projections."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    checkpoint_interval: int = Field(100, ge=1)
    batch_size: int = Field(100, ge=1)
    max_catch_up_events: int = Field(10000, ge=100)
    rebuild_batch_size: int = Field(1000, ge=100)
    enable_parallel_projections: bool = Field(True)


@dataclass(init=False)
class SagaConfig(BaseConfig):
    """Configuration for saga orchestration."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    default_timeout_seconds: float = Field(300.0, ge=1.0)
    max_retries_per_step: int = Field(3, ge=0)
    retry_delay_seconds: float = Field(1.0, ge=0.1)
    enable_compensation: bool = Field(True)
    persist_state: bool = Field(True)
    cleanup_completed_after_hours: int = Field(24, ge=1)


@dataclass(init=False)
class SnapshotConfig(BaseConfig):
    """Configuration for snapshotting behavior."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    enabled: bool = Field(True)
    strategy: SnapshotStrategy = Field(SnapshotStrategy.EVENT_COUNT)
    event_count_threshold: int = Field(100, ge=10)
    time_threshold_seconds: int = Field(3600, ge=60)
    max_snapshots_per_aggregate: int = Field(5, ge=1)


@dataclass(init=False)
class StreamingConfig(BaseConfig):
    """Configuration for event streaming."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    buffer_size: int = Field(1000, ge=100)
    batch_size: int = Field(100, ge=1)
    poll_interval_ms: int = Field(100, ge=10)
    max_subscribers: int = Field(100, ge=1)
    enable_websocket: bool = Field(True)
    websocket_ping_interval: int = Field(30, ge=5)


# ─────────────────────────────────────────────────────────────────────
# Adapter Configurations
# ─────────────────────────────────────────────────────────────────────


@dataclass(init=False)
class BaseAdapterConfig(BaseConfig):
    """Base configuration for all adapters."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    timeout: float = Field(30.0, description="Connection timeout in seconds")
    reconnect_attempts: int = Field(3, description="Number of reconnection attempts")
    reconnect_delay: float = Field(
        1.0, description="Delay between reconnection attempts"
    )
    enable_logging: bool = Field(True, description="Whether to log adapter activity")


@dataclass(init=False)
class RabbitMQConfig(BaseAdapterConfig):
    """Configuration for RabbitMQ adapter (high-level).

    For low-level adapter config, see :class:`quadkit.events.adapters.RabbitMQAdapterConfig`.
    """

    url: SecretStr = Field(..., description="AMQP connection URL")
    exchange_name: str = Field("events")
    queue_prefix: str = Field("events")
    prefetch_count: int = Field(10, ge=1)
    durable: bool = Field(True)


@dataclass(init=False)
class KafkaConfig(BaseAdapterConfig):
    """Configuration for Kafka adapter (high-level).

    For low-level adapter config, see :class:`quadkit.events.adapters.KafkaAdapterConfig`.
    """

    bootstrap_servers: str = Field(..., description="Kafka bootstrap servers")
    topic_prefix: str = Field("events")
    consumer_group: str = Field("events-consumers")
    auto_offset_reset: str = Field("earliest")
    enable_auto_commit: bool = Field(True)


@dataclass(init=False)
class AzureServiceBusConfig(BaseAdapterConfig):
    """Configuration for Azure Service Bus adapter."""

    connection_string: SecretStr = Field(
        ..., description="Service Bus connection string"
    )
    topic_name: str = Field("events")
    subscription_name: str = Field("events-subscription")
    max_concurrent_calls: int = Field(10, ge=1)


# ─────────────────────────────────────────────────────────────────────
# Top-Level Configuration
# ─────────────────────────────────────────────────────────────────────


@dataclass(init=False)
class EventsConfig(BaseConfig):
    """Top-level Events configuration.

    This consolidated class combines all event system configuration.
    No TYPE_CHECKING guards or cast() wrappers — all classes defined
    in this module, so runtime type resolution and dict→model coercion work.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(  # type: ignore[typeddict-unknown-key]
        env_prefix=const.ENV_PREFIX,
        env_nested_delimiter=const.ENV_NESTED_DELIMITER,
        extra="ignore",
    )

    config_section: ClassVar[str] = "events"

    name: str = "events"
    enabled: bool = True

    # Event Store
    event_store_backend: EventStoreBackend = Field(EventStoreBackend.MEMORY)
    postgres: PostgresEventStoreConfig | None = None
    mongodb: MongoDBEventStoreConfig | None = None
    memory: InMemoryEventStoreConfig = Field(default_factory=InMemoryEventStoreConfig)

    # Snapshots
    snapshots: SnapshotConfig = Field(default_factory=SnapshotConfig)

    # Buses
    command_bus: CommandBusConfig = Field(default_factory=CommandBusConfig)
    query_bus: QueryBusConfig = Field(default_factory=QueryBusConfig)
    event_bus: EventBusConfig = Field(default_factory=EventBusConfig)

    # Patterns
    saga: SagaConfig = Field(default_factory=SagaConfig)
    projection: ProjectionConfig = Field(default_factory=ProjectionConfig)
    streaming: StreamingConfig = Field(default_factory=StreamingConfig)

    # Version-skew alerting
    version_skew_alerts_enabled: bool = True

    # Middleware
    logging_middleware: LoggingMiddlewareConfig = Field(
        default_factory=LoggingMiddlewareConfig
    )
    validation_middleware: ValidationMiddlewareConfig = Field(
        default_factory=ValidationMiddlewareConfig
    )
    transaction_middleware: TransactionMiddlewareConfig = Field(
        default_factory=TransactionMiddlewareConfig
    )
    retry_middleware: RetryMiddlewareConfig = Field(
        default_factory=RetryMiddlewareConfig
    )
    metrics_middleware: MetricsMiddlewareConfig = Field(
        default_factory=MetricsMiddlewareConfig
    )

    # Debug/Development
    debug: bool = Field(False)
    env: Environment | None = Field(default=None, description="Deployment environment")

    # SQLite (optional)
    sqlite: SqliteConfig | None = None

    # Adapters (optional)
    rabbitmq: RabbitMQConfig | None = None
    kafka: KafkaConfig | None = None

    def validate_backend_config(self) -> list[str]:
        """Validate that the selected backend has a matching config.

        Returns a list of validation error messages. Empty list means valid.
        """
        errors: list[str] = []
        backend = self.event_store_backend
        if backend == EventStoreBackend.POSTGRES and self.postgres is None:
            errors.append(
                "event_store_backend is POSTGRES but no postgres config provided"
            )
        if backend == EventStoreBackend.MONGODB and self.mongodb is None:
            errors.append(
                "event_store_backend is MONGODB but no mongodb config provided"
            )
        if backend == EventStoreBackend.SQLITE and self.sqlite is None:
            errors.append("event_store_backend is SQLITE but no sqlite config provided")
        return errors


__all__ = [
    "AzureServiceBusConfig",
    "BaseAdapterConfig",
    "CommandBusConfig",
    "EventBusConfig",
    "EventsConfig",
    "InMemoryEventStoreConfig",
    "KafkaConfig",
    "LoggingMiddlewareConfig",
    "MetricsMiddlewareConfig",
    "MongoDBEventStoreConfig",
    "PostgresEventStoreConfig",
    "ProjectionConfig",
    "QueryBusConfig",
    "RabbitMQConfig",
    "RetryMiddlewareConfig",
    "SagaConfig",
    "SnapshotConfig",
    "SqliteConfig",
    "StreamingConfig",
    "TransactionMiddlewareConfig",
    "ValidationMiddlewareConfig",
]
