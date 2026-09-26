"""Additional unit tests for events configuration classes.

Tests EventConfig, KafkaConfig, and InMemoryEventStoreConfig edge cases.
"""

import pytest


class TestEventsConfig:
    """Tests for EventsConfig (top-level configuration)."""

    def test_events_config_defaults(self) -> None:
        """Test EventsConfig has correct defaults."""
        from quadkit.events.config import EventsConfig

        config = EventsConfig()
        assert config.name == "events"
        assert config.enabled is True
        assert config.event_store_backend.value == "memory"
        assert config.debug is False
        assert config.environment == "development"

    def test_events_config_with_memory_backend(self) -> None:
        """Test EventsConfig with memory backend."""
        from quadkit.events.config import EventsConfig
        from quadkit.events.types import EventStoreBackend

        config = EventsConfig(
            event_store_backend=EventStoreBackend.MEMORY,
        )
        assert config.event_store_backend == EventStoreBackend.MEMORY
        assert config.memory is not None
        assert config.memory.max_events_per_stream == 10000

    def test_events_config_with_postgres_backend(self) -> None:
        """Test EventsConfig with postgres backend."""
        from quadkit.events.config import EventsConfig, PostgresEventStoreConfig
        from quadkit.events.types import EventStoreBackend

        config = EventsConfig(
            event_store_backend=EventStoreBackend.POSTGRES,
            postgres=PostgresEventStoreConfig(
                host="localhost",
                database="events",
            ),
        )
        assert config.event_store_backend == EventStoreBackend.POSTGRES
        assert config.postgres is not None

    def test_events_config_with_mongodb_backend(self) -> None:
        """Test EventsConfig with mongodb backend."""
        from quadkit.events.config import EventsConfig, MongoDBEventStoreConfig
        from quadkit.events.types import EventStoreBackend

        config = EventsConfig(
            event_store_backend=EventStoreBackend.MONGODB,
            mongodb=MongoDBEventStoreConfig(
                connection_string="mongodb://localhost:27017",
            ),
        )
        assert config.event_store_backend == EventStoreBackend.MONGODB
        assert config.mongodb is not None

    def test_events_config_nested_configs(self) -> None:
        """Test EventsConfig has all nested config objects."""
        from quadkit.events.config import (
            EventsConfig,
            CommandBusConfig,
            QueryBusConfig,
            EventBusConfig,
            SagaConfig,
            ProjectionConfig,
            StreamingConfig,
            LoggingMiddlewareConfig,
            ValidationMiddlewareConfig,
            TransactionMiddlewareConfig,
            RetryMiddlewareConfig,
            MetricsMiddlewareConfig,
            SnapshotConfig,
        )

        config = EventsConfig()

        assert isinstance(config.command_bus, CommandBusConfig)
        assert isinstance(config.query_bus, QueryBusConfig)
        assert isinstance(config.event_bus, EventBusConfig)
        assert isinstance(config.saga, SagaConfig)
        assert isinstance(config.projection, ProjectionConfig)
        assert isinstance(config.streaming, StreamingConfig)
        assert isinstance(config.logging_middleware, LoggingMiddlewareConfig)
        assert isinstance(config.validation_middleware, ValidationMiddlewareConfig)
        assert isinstance(config.transaction_middleware, TransactionMiddlewareConfig)
        assert isinstance(config.retry_middleware, RetryMiddlewareConfig)
        assert isinstance(config.metrics_middleware, MetricsMiddlewareConfig)
        assert isinstance(config.snapshots, SnapshotConfig)

    def test_events_config_validation(self) -> None:
        """Test EventsConfig.validate_backend_config()."""
        from quadkit.events.config import EventsConfig
        from quadkit.events.types import EventStoreBackend

        config = EventsConfig(
            event_store_backend=EventStoreBackend.MEMORY,
        )
        errors = config.validate_backend_config()
        assert errors == []

    def test_events_config_validation_postgres_missing(self) -> None:
        """Test EventsConfig validation fails when postgres config missing."""
        from quadkit.events.config import EventsConfig
        from quadkit.events.types import EventStoreBackend

        config = EventsConfig(
            event_store_backend=EventStoreBackend.POSTGRES,
        )
        errors = config.validate_backend_config()
        assert len(errors) == 1
        assert "POSTGRES" in errors[0]

    def test_events_config_validation_mongodb_missing(self) -> None:
        """Test EventsConfig validation fails when mongodb config missing."""
        from quadkit.events.config import EventsConfig
        from quadkit.events.types import EventStoreBackend

        config = EventsConfig(
            event_store_backend=EventStoreBackend.MONGODB,
        )
        errors = config.validate_backend_config()
        assert len(errors) == 1
        assert "MONGODB" in errors[0]

    def test_events_config_with_adapters(self) -> None:
        """Test EventsConfig with adapter configs."""
        from quadkit.events.config import EventsConfig, KafkaConfig, RabbitMQConfig

        config = EventsConfig(
            kafka=KafkaConfig(bootstrap_servers="localhost:9092"),
            rabbitmq=RabbitMQConfig(url="amqp://localhost:5672/"),
        )
        assert config.kafka is not None
        assert config.rabbitmq is not None

    def test_events_config_debug_mode(self) -> None:
        """Test EventsConfig debug mode."""
        from quadkit.events.config import EventsConfig

        config = EventsConfig(debug=True, env="production")
        assert config.debug is True
        assert config.env == "production"

    def test_events_config_custom_batch_sizes(self) -> None:
        """Test EventsConfig with custom batch sizes."""
        from quadkit.events.config import EventsConfig

        config = EventsConfig()
        assert config.projection.batch_size == 100
        assert config.projection.checkpoint_interval == 100
        assert config.streaming.batch_size == 100


class TestKafkaConfigEdgeCases:
    """Edge case tests for KafkaConfig."""

    def test_kafka_config_all_required_fields(self) -> None:
        """Test KafkaConfig with all required fields only."""
        from quadkit.events.config import KafkaConfig

        config = KafkaConfig(bootstrap_servers="localhost:9092")
        assert config.bootstrap_servers == "localhost:9092"

    def test_kafka_config_multiple_servers(self) -> None:
        """Test KafkaConfig with multiple servers."""
        from quadkit.events.config import KafkaConfig

        config = KafkaConfig(
            bootstrap_servers="broker1:9092,broker2:9092,broker3:9092",
        )
        assert "," in config.bootstrap_servers

    def test_kafka_config_auto_offset_options(self) -> None:
        """Test KafkaConfig auto_offset_reset options."""
        from quadkit.events.config import KafkaConfig

        for offset_reset in ["earliest", "latest", "none"]:
            config = KafkaConfig(
                bootstrap_servers="localhost:9092",
                auto_offset_reset=offset_reset,
            )
            assert config.auto_offset_reset == offset_reset


class TestInMemoryEventStoreConfigEdgeCases:
    """Edge case tests for InMemoryEventStoreConfig."""

    def test_in_memory_config_max_events_boundary(self) -> None:
        """Test InMemoryEventStoreConfig max_events_per_stream boundary."""
        from quadkit.events.config import InMemoryEventStoreConfig

        config = InMemoryEventStoreConfig(max_events_per_stream=100)
        assert config.max_events_per_stream == 100

        config = InMemoryEventStoreConfig(max_events_per_stream=100000)
        assert config.max_events_per_stream == 100000

    def test_in_memory_config_snapshot_toggle(self) -> None:
        """Test InMemoryEventStoreConfig enable_snapshots toggle."""
        from quadkit.events.config import InMemoryEventStoreConfig

        config = InMemoryEventStoreConfig(enable_snapshots=True)
        assert config.enable_snapshots is True

        config = InMemoryEventStoreConfig(enable_snapshots=False)
        assert config.enable_snapshots is False

    def test_in_memory_config_default_factory(self) -> None:
        """Test InMemoryEventStoreConfig default factory creates new instance."""
        from quadkit.events.config import InMemoryEventStoreConfig

        config1 = InMemoryEventStoreConfig()
        config2 = InMemoryEventStoreConfig()
        assert config1.max_events_per_stream == config2.max_events_per_stream
        assert config1.enable_snapshots == config2.enable_snapshots