"""Tests for events config sagas."""

import pytest


class TestSagaConfig:
    """Tests for SagaConfig."""

    def test_saga_config_defaults(self) -> None:
        """Test SagaConfig has correct defaults."""
        from quadkit.events.config import SagaConfig

        config = SagaConfig()
        assert config.default_timeout_seconds == 300.0
        assert config.max_retries_per_step == 3
        assert config.retry_delay_seconds == 1.0
        assert config.enable_compensation is True
        assert config.persist_state is True
        assert config.cleanup_completed_after_hours == 24

    def test_saga_config_custom(self) -> None:
        """Test SagaConfig with custom values."""
        from quadkit.events.config import SagaConfig

        config = SagaConfig(
            default_timeout_seconds=600.0,
            max_retries_per_step=5,
            retry_delay_seconds=2.0,
            enable_compensation=False,
            persist_state=False,
            cleanup_completed_after_hours=48,
        )
        assert config.default_timeout_seconds == 600.0
        assert config.max_retries_per_step == 5
        assert config.retry_delay_seconds == 2.0
        assert config.enable_compensation is False
        assert config.persist_state is False
        assert config.cleanup_completed_after_hours == 48
