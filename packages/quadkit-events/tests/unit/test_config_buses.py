"""Tests for events config buses."""

import pytest


class TestCommandBusConfig:
    """Tests for CommandBusConfig."""

    def test_command_bus_config_defaults(self) -> None:
        """Test CommandBusConfig has correct defaults."""
        from quadkit.events.config import CommandBusConfig

        config = CommandBusConfig()
        assert config.max_retries == 3
        assert config.retry_delay_seconds == 1.0
        assert config.timeout_seconds == 30.0
        assert config.enable_validation is True
        assert config.enable_logging is True
        assert config.enable_metrics is True

    def test_command_bus_config_custom(self) -> None:
        """Test CommandBusConfig with custom values."""
        from quadkit.events.config import CommandBusConfig

        config = CommandBusConfig(
            max_retries=5,
            retry_delay_seconds=2.0,
            timeout_seconds=60.0,
            enable_validation=False,
            enable_logging=False,
            enable_metrics=False,
        )
        assert config.max_retries == 5
        assert config.retry_delay_seconds == 2.0
        assert config.timeout_seconds == 60.0
        assert config.enable_validation is False
        assert config.enable_logging is False
        assert config.enable_metrics is False


class TestQueryBusConfig:
    """Tests for QueryBusConfig."""

    def test_query_bus_config_defaults(self) -> None:
        """Test QueryBusConfig has correct defaults."""
        from quadkit.events.config import QueryBusConfig

        config = QueryBusConfig()
        assert config.timeout_seconds == 30.0
        assert config.enable_logging is True
        assert config.enable_metrics is True

    def test_query_bus_config_custom(self) -> None:
        """Test QueryBusConfig with custom values."""
        from quadkit.events.config import QueryBusConfig

        config = QueryBusConfig(
            timeout_seconds=60.0,
            enable_logging=False,
            enable_metrics=False,
        )
        assert config.timeout_seconds == 60.0
        assert config.enable_logging is False
        assert config.enable_metrics is False


class TestEventBusConfig:
    """Tests for EventBusConfig."""

    def test_event_bus_config_defaults(self) -> None:
        """Test EventBusConfig has correct defaults."""
        from quadkit.events.config import EventBusConfig

        config = EventBusConfig()
        assert config.max_concurrent_handlers == 10
        assert config.handler_timeout_seconds == 30.0
        assert config.retry_failed_handlers is True
        assert config.max_handler_retries == 3
        assert config.enable_dead_letter is True
        assert config.allow_no_handlers is True
        assert config.parallel_dispatch is True
        assert config.continue_on_error is True
        assert config.max_queue_per_subscriber == 1000

    def test_event_bus_config_custom(self) -> None:
        """Test EventBusConfig with custom values."""
        from quadkit.events.config import EventBusConfig

        config = EventBusConfig(
            max_concurrent_handlers=5,
            handler_timeout_seconds=60.0,
            retry_failed_handlers=False,
            max_handler_retries=5,
            enable_dead_letter=False,
            allow_no_handlers=False,
            parallel_dispatch=False,
            continue_on_error=False,
            max_queue_per_subscriber=500,
        )
        assert config.max_concurrent_handlers == 5
        assert config.handler_timeout_seconds == 60.0
        assert config.retry_failed_handlers is False
        assert config.max_handler_retries == 5
        assert config.enable_dead_letter is False
        assert config.allow_no_handlers is False
        assert config.parallel_dispatch is False
        assert config.continue_on_error is False
        assert config.max_queue_per_subscriber == 500
