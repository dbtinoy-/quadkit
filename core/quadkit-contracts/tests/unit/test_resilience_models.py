"""Tests for resilience configuration models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass, replace

import pytest

from quadkit.contracts.infra.resilience.models import (
    CircuitBreakerConfig,
    RetryConfig,
    TimeoutConfig,
)


class TestRetryConfig:
    """Tests for RetryConfig."""

    def test_default_values(self) -> None:
        """Test RetryConfig has correct defaults."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.backoff_factor == 2.0
        assert config.jitter is True
        assert config.retry_on == (Exception,)
        assert config.retry_if is None
        assert config.on_retry is None
        assert config.retry_sync is False

    def test_custom_values(self) -> None:
        """Test RetryConfig with custom values."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=30.0,
            backoff_factor=1.5,
            jitter=False,
        )
        assert config.max_attempts == 5
        assert config.base_delay == 0.5
        assert config.max_delay == 30.0
        assert config.backoff_factor == 1.5
        assert config.jitter is False

    def test_frozen_dataclass(self) -> None:
        """Test RetryConfig is frozen (immutable)."""
        config = RetryConfig()
        with pytest.raises(FrozenInstanceError):
            config.max_attempts = 10

    def test_max_attempts_minimum(self) -> None:
        """Test max_attempts can be 1 (no retries)."""
        config = RetryConfig(max_attempts=1)
        assert config.max_attempts == 1


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig."""

    def test_default_values(self) -> None:
        """Test CircuitBreakerConfig has correct defaults."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60.0
        assert config.expected_exception == (Exception,)
        assert config.success_threshold == 3
        assert config.timeout == 30.0
        assert config.name == ""
        assert config.sliding_window_seconds == 60.0
        assert config.failure_rate_threshold == 0.5
        assert config.backend == "memory"

    def test_custom_values(self) -> None:
        """Test CircuitBreakerConfig with custom values."""
        config = CircuitBreakerConfig(
            failure_threshold=10,
            recovery_timeout=120.0,
            success_threshold=5,
            timeout=60.0,
            name="my_breaker",
            backend="redis",
        )
        assert config.failure_threshold == 10
        assert config.recovery_timeout == 120.0
        assert config.success_threshold == 5
        assert config.timeout == 60.0
        assert config.name == "my_breaker"
        assert config.backend == "redis"

    def test_frozen_dataclass(self) -> None:
        """Test CircuitBreakerConfig is frozen (immutable)."""
        config = CircuitBreakerConfig()
        with pytest.raises(FrozenInstanceError):
            config.failure_threshold = 20

    def test_valid_backends(self) -> None:
        """Test all valid backend values."""
        for backend in ("memory", "redis", "consul"):
            config = CircuitBreakerConfig(backend=backend)
            assert config.backend == backend


class TestTimeoutConfig:
    """Tests for TimeoutConfig."""

    def test_default_values(self) -> None:
        """Test TimeoutConfig has correct defaults."""
        config = TimeoutConfig()
        assert config.timeout == 30.0
        assert config.timeout_message == "Operation timed out"

    def test_custom_values(self) -> None:
        """Test TimeoutConfig with custom values."""
        config = TimeoutConfig(timeout=60.0, timeout_message="Custom timeout")
        assert config.timeout == 60.0
        assert config.timeout_message == "Custom timeout"

    def test_frozen_dataclass(self) -> None:
        """Test TimeoutConfig is frozen (immutable)."""
        config = TimeoutConfig()
        with pytest.raises(FrozenInstanceError):
            config.timeout = 100.0


class TestResilienceModelsIntegration:
    """Integration tests for resilience models."""

    def test_can_use_in_dataclass(self) -> None:
        """Test resilience configs can be used as fields."""

        @dataclass
        class ServiceConfig:
            retry: RetryConfig
            circuit_breaker: CircuitBreakerConfig
            timeout: TimeoutConfig

        config = ServiceConfig(
            retry=RetryConfig(max_attempts=2),
            circuit_breaker=CircuitBreakerConfig(name="service"),
            timeout=TimeoutConfig(timeout=15.0),
        )
        assert config.retry.max_attempts == 2
        assert config.circuit_breaker.name == "service"
        assert config.timeout.timeout == 15.0

    def test_can_copy_with_replace(self) -> None:
        """Test configs can be copied with replace."""
        original = RetryConfig(max_attempts=3, base_delay=1.0)
        modified = replace(original, max_attempts=5)
        assert original.max_attempts == 3
        assert modified.max_attempts == 5
        assert modified.base_delay == 1.0
