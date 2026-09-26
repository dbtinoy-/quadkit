"""Additional unit tests for events config classes - command/query/event bus configs."""

from __future__ import annotations

from quadkit.events.config import (
    CommandBusConfig,
    EventBusConfig,
    EventsConfig,
    QueryBusConfig,
)


class TestCommandBusConfig:
    """Tests for CommandBusConfig."""

    def test_command_bus_config_defaults(self) -> None:
        """Test CommandBusConfig has correct defaults."""
        config = CommandBusConfig()
        assert config.max_retries == 3
        assert config.timeout_seconds == 30.0
        assert config.retry_delay_seconds == 1.0

    def test_command_bus_config_custom_values(self) -> None:
        """Test CommandBusConfig with custom values."""
        config = CommandBusConfig(
            max_retries=5,
            timeout_seconds=60.0,
        )
        assert config.max_retries == 5
        assert config.timeout_seconds == 60.0

    def test_command_bus_config_retry_delays(self) -> None:
        """Test CommandBusConfig retry delay options."""
        config = CommandBusConfig(retry_delay_seconds=2.5)
        assert config.retry_delay_seconds == 2.5


class TestQueryBusConfig:
    """Tests for QueryBusConfig."""

    def test_query_bus_config_defaults(self) -> None:
        """Test QueryBusConfig has correct defaults."""
        config = QueryBusConfig()
        assert config.timeout_seconds == 30.0
        assert config.enable_logging is True
        assert config.enable_metrics is True

    def test_query_bus_config_custom_values(self) -> None:
        """Test QueryBusConfig with custom values."""
        config = QueryBusConfig(
            timeout_seconds=60.0,
            enable_logging=False,
        )
        assert config.timeout_seconds == 60.0
        assert config.enable_logging is False


class TestEventBusConfig:
    """Tests for EventBusConfig."""

    def test_event_bus_config_defaults(self) -> None:
        """Test EventBusConfig has correct defaults."""
        config = EventBusConfig()
        assert config.max_concurrent_handlers == 10
        assert config.handler_timeout_seconds == 30.0
        assert config.retry_failed_handlers is True

    def test_event_bus_config_custom_values(self) -> None:
        """Test EventBusConfig with custom values."""
        config = EventBusConfig(
            max_concurrent_handlers=50,
            retry_failed_handlers=False,
        )
        assert config.max_concurrent_handlers == 50
        assert config.retry_failed_handlers is False


class TestEventsConfigBusIntegration:
    """Test EventsConfig bus integration."""

    def test_events_config_command_bus_instance(self) -> None:
        """Test EventsConfig creates CommandBusConfig instance."""
        config = EventsConfig()
        assert isinstance(config.command_bus, CommandBusConfig)

    def test_events_config_query_bus_instance(self) -> None:
        """Test EventsConfig creates QueryBusConfig instance."""
        config = EventsConfig()
        assert isinstance(config.query_bus, QueryBusConfig)

    def test_events_config_event_bus_instance(self) -> None:
        """Test EventsConfig creates EventBusConfig instance."""
        config = EventsConfig()
        assert isinstance(config.event_bus, EventBusConfig)

    def test_events_config_bus_defaults_inherited(self) -> None:
        """Test bus configs inherit default values from EventsConfig."""
        config = EventsConfig(debug=True)
        assert config.command_bus is not None
        assert config.query_bus is not None
        assert config.event_bus is not None
