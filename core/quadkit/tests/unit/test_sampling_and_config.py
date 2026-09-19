"""Log sampling and logging-config model tests."""

from __future__ import annotations

import pytest
import structlog

from quadkit.logging import apply_config, configure_logging, get_logger, reset_logging
from quadkit.logging.config import LoggingConfig, RedactionConfig, SamplingConfig

# ---------------------------------------------------------------------------
# Stdlib bridge
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _cleanup_stdlib_handlers() -> None:
    """Remove handlers added by TestStdlibBridge to avoid cross-test pollution."""
    yield
    reset_logging()



class TestLogSampling:
    """Test deterministic log sampling via _sampling_processor."""

    def test_sampling_disabled_by_default(self) -> None:
        """Sampling is disabled by default — all events pass."""
        from quadkit.logging.processors import _sampling_processor

        configure_logging()  # defaults: sampling_enabled=False

        event_dict = {"event": "high_volume"}
        result = _sampling_processor(None, "info", event_dict)
        assert result is event_dict

    def test_sampling_always_passes_warnings(self) -> None:
        """WARNING+ events are never sampled, even at rate=0."""
        from quadkit.logging.processors import _sampling_processor

        configure_logging(
            sampling_enabled=True,
            sampling_default_rate=0.0,  # drop everything
        )

        event_dict = {"event": "critical_failure"}
        result = _sampling_processor(None, "warning", event_dict)
        assert result is event_dict

        result = _sampling_processor(None, "error", event_dict)
        assert result is event_dict

        result = _sampling_processor(None, "critical", event_dict)
        assert result is event_dict

    def test_sampling_rate_zero_drops_debug_info(self) -> None:
        """rate=0.0 drops all DEBUG/INFO events."""
        from quadkit.logging.processors import _sampling_processor

        configure_logging(
            sampling_enabled=True,
            sampling_default_rate=0.0,
        )

        event_dict = {"event": "chatty_event"}
        with pytest.raises(structlog.DropEvent):
            _sampling_processor(None, "debug", event_dict)

        with pytest.raises(structlog.DropEvent):
            _sampling_processor(None, "info", event_dict)

    def test_sampling_rate_1_passes_all(self) -> None:
        """rate=1.0 passes all events (no sampling)."""
        from quadkit.logging.processors import _sampling_processor

        configure_logging(
            sampling_enabled=True,
            sampling_default_rate=1.0,
        )

        event_dict = {"event": "any_event"}
        result = _sampling_processor(None, "info", event_dict)
        assert result is event_dict

    def test_sampling_per_event_rule(self) -> None:
        """Per-event rules override default rate."""
        from quadkit.logging.processors import _sampling_processor

        configure_logging(
            sampling_enabled=True,
            sampling_default_rate=1.0,  # default: pass all
            sampling_rules={"drop_me": 0.0},  # but this event: drop all
        )

        event_dict = {"event": "drop_me"}
        with pytest.raises(structlog.DropEvent):
            _sampling_processor(None, "info", event_dict)

        # Other events still pass
        event_dict_ok = {"event": "keep_me"}
        result = _sampling_processor(None, "info", event_dict_ok)
        assert result is event_dict_ok

    def test_sampling_is_deterministic(self) -> None:
        """Same event key always produces same include/exclude decision."""
        from quadkit.logging.processors import _sampling_processor

        configure_logging(
            sampling_enabled=True,
            sampling_default_rate=0.5,
        )

        # Run the same event 100 times — should always get the same result
        event_dict = {"event": "deterministic_test"}
        results = []
        for _ in range(100):
            try:
                _sampling_processor(None, "info", dict(event_dict))
                results.append(True)
            except structlog.DropEvent:
                results.append(False)

        # All results should be the same (deterministic)
        assert len(set(results)) == 1


# ---------------------------------------------------------------------------
# LoggingConfig model
# ---------------------------------------------------------------------------


class TestLoggingConfigModel:
    """Test LoggingConfig and SamplingConfig models."""

    def test_default_values(self) -> None:
        """LoggingConfig has sensible defaults."""
        config = LoggingConfig()
        assert config.level == "INFO"
        assert config.json_format is False
        assert config.levels == {}
        assert isinstance(config.sampling, SamplingConfig)
        assert isinstance(config.redaction, RedactionConfig)
        assert config.redaction.enabled is True

    def test_sampling_config_defaults(self) -> None:
        """SamplingConfig has sensible defaults."""
        sampling = SamplingConfig()
        assert sampling.enabled is False
        assert sampling.default_rate == 1.0
        assert sampling.rules == {}

    def test_logging_config_with_levels(self) -> None:
        """LoggingConfig accepts per-logger levels."""
        config = LoggingConfig(
            level="DEBUG",
            levels={"quadkit.di": "WARNING"},
        )
        assert config.levels == {"quadkit.di": "WARNING"}

    def test_logging_config_with_sampling(self) -> None:
        """LoggingConfig accepts nested SamplingConfig."""
        config = LoggingConfig(
            sampling=SamplingConfig(enabled=True, default_rate=0.5),
        )
        assert config.sampling.enabled is True
        assert config.sampling.default_rate == 0.5

    def test_logging_config_with_redaction(self) -> None:
        """LoggingConfig accepts nested RedactionConfig."""
        config = LoggingConfig(
            redaction=RedactionConfig(enabled=False, field_denylist=("a",)),
        )
        assert config.redaction.enabled is False
        assert config.redaction.field_denylist == ("a",)

    def test_logging_config_redaction_from_dict(self) -> None:
        """LoggingConfig redaction can be constructed from nested dict."""
        config = LoggingConfig(
            redaction={"enabled": False, "field_denylist": ("a",)},
        )
        assert config.redaction.enabled is False
        assert config.redaction.field_denylist == ("a",)

    def test_logging_config_from_dict(self) -> None:
        """LoggingConfig can be constructed from nested dict."""
        config = LoggingConfig(
            level="WARNING",
            sampling={"enabled": True, "default_rate": 0.1},
        )
        assert config.sampling.enabled is True
        assert config.sampling.default_rate == 0.1

    def test_invalid_level_normalized(self) -> None:
        """Invalid log level is normalized to INFO."""
        config = LoggingConfig(level="NOPE")
        assert config.level == "INFO"

    def test_no_file_field(self) -> None:
        """LoggingConfig no longer has a 'file' field (removed Phase 2)."""
        dc_fields = getattr(LoggingConfig, "__dataclass_fields__", {})
        assert "file" not in dc_fields

    def test_no_stream_field(self) -> None:
        """LoggingConfig no longer has a 'stream' field (removed Phase 2)."""
        dc_fields = getattr(LoggingConfig, "__dataclass_fields__", {})
        assert "stream" not in dc_fields


# ---------------------------------------------------------------------------
# apply_config integration
# ---------------------------------------------------------------------------


