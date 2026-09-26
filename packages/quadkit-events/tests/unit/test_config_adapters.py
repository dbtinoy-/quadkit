"""Tests for events config adapters."""

import pytest


class TestBaseAdapterConfig:
    """Tests for BaseAdapterConfig."""

    def test_base_adapter_config_defaults(self) -> None:
        """Test BaseAdapterConfig has correct defaults."""
        from quadkit.events.config import BaseAdapterConfig

        config = BaseAdapterConfig()
        assert config.timeout == 30.0
        assert config.reconnect_attempts == 3
        assert config.reconnect_delay == 1.0
        assert config.enable_logging is True

    def test_base_adapter_config_custom(self) -> None:
        """Test BaseAdapterConfig with custom values."""
        from quadkit.events.config import BaseAdapterConfig

        config = BaseAdapterConfig(
            timeout=60.0,
            reconnect_attempts=5,
            reconnect_delay=2.0,
            enable_logging=False,
        )
        assert config.timeout == 60.0
        assert config.reconnect_attempts == 5
        assert config.reconnect_delay == 2.0
        assert config.enable_logging is False


class TestRabbitMQConfig:
    """Tests for RabbitMQConfig."""

    def test_rabbitmq_config_defaults(self) -> None:
        """Test RabbitMQConfig has correct defaults."""
        from quadkit.events.config import RabbitMQConfig

        config = RabbitMQConfig(url="amqp://guest:guest@localhost:5672/")
        assert config.exchange_name == "events"
        assert config.queue_prefix == "events"
        assert config.prefetch_count == 10
        assert config.durable is True

    def test_rabbitmq_config_custom(self) -> None:
        """Test RabbitMQConfig with custom values."""
        from quadkit.events.config import RabbitMQConfig

        config = RabbitMQConfig(
            url="amqp://guest:guest@localhost:5672/",
            exchange_name="my_exchange",
            queue_prefix="my_queue",
            prefetch_count=5,
            durable=False,
        )
        assert config.exchange_name == "my_exchange"
        assert config.queue_prefix == "my_queue"
        assert config.prefetch_count == 5
        assert config.durable is False


class TestKafkaConfig:
    """Tests for KafkaConfig."""

    def test_kafka_config_defaults(self) -> None:
        """Test KafkaConfig has correct defaults."""
        from quadkit.events.config import KafkaConfig

        config = KafkaConfig(bootstrap_servers="localhost:9092")
        assert config.topic_prefix == "events"
        assert config.consumer_group == "events-consumers"
        assert config.auto_offset_reset == "earliest"
        assert config.enable_auto_commit is True

    def test_kafka_config_custom(self) -> None:
        """Test KafkaConfig with custom values."""
        from quadkit.events.config import KafkaConfig

        config = KafkaConfig(
            bootstrap_servers="localhost:9092",
            topic_prefix="my_topic",
            consumer_group="my_group",
            auto_offset_reset="latest",
            enable_auto_commit=False,
        )
        assert config.topic_prefix == "my_topic"
        assert config.consumer_group == "my_group"
        assert config.auto_offset_reset == "latest"
        assert config.enable_auto_commit is False


class TestAzureServiceBusConfig:
    """Tests for AzureServiceBusConfig."""

    def test_azure_service_bus_config_defaults(self) -> None:
        """Test AzureServiceBusConfig has correct defaults."""
        from quadkit.events.config import AzureServiceBusConfig

        config = AzureServiceBusConfig(connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=Test;SharedAccessKey=TestKey123")
        assert config.topic_name == "events"
        assert config.subscription_name == "events-subscription"
        assert config.max_concurrent_calls == 10

    def test_azure_service_bus_config_custom(self) -> None:
        """Test AzureServiceBusConfig with custom values."""
        from quadkit.events.config import AzureServiceBusConfig

        config = AzureServiceBusConfig(
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=Test;SharedAccessKey=TestKey123",
            topic_name="my_topic",
            subscription_name="my_subscription",
            max_concurrent_calls=5,
        )
        assert config.topic_name == "my_topic"
        assert config.subscription_name == "my_subscription"
        assert config.max_concurrent_calls == 5
