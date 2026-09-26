"""Tests for events config middleware."""

import pytest


class TestLoggingMiddlewareConfig:
    """Tests for LoggingMiddlewareConfig."""

    def test_logging_middleware_config_defaults(self) -> None:
        """Test LoggingMiddlewareConfig has correct defaults."""
        from quadkit.events.config import LoggingMiddlewareConfig

        config = LoggingMiddlewareConfig()
        assert config.enabled is True
        assert config.log_level == "INFO"
        assert config.include_payload is False
        assert config.max_payload_length == 1000

    def test_logging_middleware_config_custom(self) -> None:
        """Test LoggingMiddlewareConfig with custom values."""
        from quadkit.events.config import LoggingMiddlewareConfig

        config = LoggingMiddlewareConfig(
            enabled=False,
            log_level="DEBUG",
            include_payload=True,
            max_payload_length=2000,
        )
        assert config.enabled is False
        assert config.log_level == "DEBUG"
        assert config.include_payload is True
        assert config.max_payload_length == 2000


class TestValidationMiddlewareConfig:
    """Tests for ValidationMiddlewareConfig."""

    def test_validation_middleware_config_defaults(self) -> None:
        """Test ValidationMiddlewareConfig has correct defaults."""
        from quadkit.events.config import ValidationMiddlewareConfig

        config = ValidationMiddlewareConfig()
        assert config.enabled is True
        assert config.strict_mode is True

    def test_validation_middleware_config_custom(self) -> None:
        """Test ValidationMiddlewareConfig with custom values."""
        from quadkit.events.config import ValidationMiddlewareConfig

        config = ValidationMiddlewareConfig(
            enabled=False,
            strict_mode=False,
        )
        assert config.enabled is False
        assert config.strict_mode is False


class TestTransactionMiddlewareConfig:
    """Tests for TransactionMiddlewareConfig."""

    def test_transaction_middleware_config_defaults(self) -> None:
        """Test TransactionMiddlewareConfig has correct defaults."""
        from quadkit.events.config import TransactionMiddlewareConfig

        config = TransactionMiddlewareConfig()
        assert config.enabled is True
        assert config.isolation_level == "READ_COMMITTED"
        assert config.timeout_seconds == 30.0

    def test_transaction_middleware_config_custom(self) -> None:
        """Test TransactionMiddlewareConfig with custom values."""
        from quadkit.events.config import TransactionMiddlewareConfig

        config = TransactionMiddlewareConfig(
            enabled=False,
            isolation_level="SERIALIZABLE",
            timeout_seconds=60.0,
        )
        assert config.enabled is False
        assert config.isolation_level == "SERIALIZABLE"
        assert config.timeout_seconds == 60.0


class TestRetryMiddlewareConfig:
    """Tests for RetryMiddlewareConfig."""

    def test_retry_middleware_config_defaults(self) -> None:
        """Test RetryMiddlewareConfig has correct defaults."""
        from quadkit.events.config import RetryMiddlewareConfig

        config = RetryMiddlewareConfig()
        assert config.enabled is True
        assert config.max_retries == 3
        assert config.initial_delay_seconds == 0.1
        assert config.max_delay_seconds == 10.0
        assert config.exponential_base == 2.0

    def test_retry_middleware_config_custom(self) -> None:
        """Test RetryMiddlewareConfig with custom values."""
        from quadkit.events.config import RetryMiddlewareConfig

        config = RetryMiddlewareConfig(
            enabled=False,
            max_retries=5,
            initial_delay_seconds=0.5,
            max_delay_seconds=30.0,
            exponential_base=3.0,
        )
        assert config.enabled is False
        assert config.max_retries == 5
        assert config.initial_delay_seconds == 0.5
        assert config.max_delay_seconds == 30.0
        assert config.exponential_base == 3.0


class TestMetricsMiddlewareConfig:
    """Tests for MetricsMiddlewareConfig."""

    def test_metrics_middleware_config_defaults(self) -> None:
        """Test MetricsMiddlewareConfig has correct defaults."""
        from quadkit.events.config import MetricsMiddlewareConfig

        config = MetricsMiddlewareConfig()
        assert config.enabled is True
        assert config.prefix == "events"
        assert config.include_histograms is True
        assert config.histogram_buckets == [0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

    def test_metrics_middleware_config_custom(self) -> None:
        """Test MetricsMiddlewareConfig with custom values."""
        from quadkit.events.config import MetricsMiddlewareConfig

        config = MetricsMiddlewareConfig(
            enabled=False,
            prefix="my_prefix",
            include_histograms=False,
            histogram_buckets=[0.1, 1.0, 10.0],
        )
        assert config.enabled is False
        assert config.prefix == "my_prefix"
        assert config.include_histograms is False
        assert config.histogram_buckets == [0.1, 1.0, 10.0]
