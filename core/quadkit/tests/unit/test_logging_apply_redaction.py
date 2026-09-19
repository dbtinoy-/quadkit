"""ApplyConfig and redaction end-to-end tests."""

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



class TestApplyConfig:
    """Test apply_config() integrates LoggingConfig with configure_logging()."""

    def test_basic_apply(self) -> None:
        """apply_config() calls configure_logging() with correct args."""
        config = LoggingConfig(level="DEBUG", json_format=True)
        apply_config(config)
        # If we got here without error, it worked

    def test_apply_with_levels(self) -> None:
        """apply_config() passes per-logger levels through."""
        config = LoggingConfig(
            levels={"quadkit.di": "ERROR"},
        )
        apply_config(config)

        from quadkit.logging.processors import _state
        assert "quadkit.di" in _state.logger_levels

    def test_apply_with_service_name(self) -> None:
        """apply_config() forwards service_name to the pipeline state."""
        config = LoggingConfig()
        apply_config(config, service_name="orders")

        from quadkit.logging.processors import _state
        assert _state.service_name == "orders"

    def test_apply_with_sampling(self) -> None:
        """apply_config() passes sampling config through."""
        config = LoggingConfig(
            sampling=SamplingConfig(enabled=True, default_rate=0.5),
        )
        apply_config(config)

        from quadkit.logging.processors import _state
        assert _state.sampling_enabled is True
        assert _state.sampling_default_rate == 0.5

    def test_apply_redaction_enabled_default(self) -> None:
        """apply_config() installs a DefaultRedactor by default."""
        config = LoggingConfig()
        apply_config(config)

        from quadkit.logging.redaction import DefaultRedactor, get_redactor
        assert isinstance(get_redactor(), DefaultRedactor)

    def test_apply_redaction_explicit_enabled(self) -> None:
        """apply_config() installs a DefaultRedactor when enabled."""
        config = LoggingConfig(redaction=RedactionConfig(enabled=True))
        apply_config(config)

        from quadkit.logging.redaction import DefaultRedactor, get_redactor
        assert isinstance(get_redactor(), DefaultRedactor)

    def test_apply_redaction_disabled(self) -> None:
        """apply_config() installs a NoOpRedactor when disabled."""
        config = LoggingConfig(redaction=RedactionConfig(enabled=False))
        apply_config(config)

        from quadkit.logging.redaction import NoOpRedactor, get_redactor
        assert isinstance(get_redactor(), NoOpRedactor)

    def test_apply_redaction_custom_denylist(self) -> None:
        """apply_config() forwards a custom field denylist."""
        config = LoggingConfig(
            redaction=RedactionConfig(enabled=True, field_denylist=("ssn",)),
        )
        apply_config(config)

        from quadkit.logging.redaction import DefaultRedactor, get_redactor
        redactor = get_redactor()
        assert isinstance(redactor, DefaultRedactor)
        assert redactor._field_denylist == frozenset({"ssn"})


# ---------------------------------------------------------------------------
# End-to-end redaction through the real pipeline
# ---------------------------------------------------------------------------


class TestRedactionE2E:
    """Prove redaction works through the full structlog pipeline."""

    def test_password_field_redacted(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A denylisted key is masked in JSON output."""
        configure_logging(level="DEBUG", json_format=True)

        logger = get_logger()
        logger.info("payment_failed", password="hunter2", user_id=7)

        captured = capsys.readouterr()
        outerr = captured.out + captured.err
        assert "<redacted>" in outerr
        assert "hunter2" not in outerr

    def test_nested_key_redacted(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Nested denylisted keys are masked recursively."""
        configure_logging(level="DEBUG", json_format=True)

        logger = get_logger()
        logger.info("request_started", metadata={"api_key": "x", "user": "bob"})

        captured = capsys.readouterr()
        outerr = captured.out + captured.err
        assert "<redacted>" in outerr
        assert '"x"' not in outerr
        assert "bob" in outerr

    def test_redaction_disabled_passes_raw(self, capsys: pytest.CaptureFixture[str]) -> None:
        """configure_logging(redaction_enabled=False) passes raw values."""
        configure_logging(level="DEBUG", json_format=True, redaction_enabled=False)

        logger = get_logger()
        logger.info("payment_failed", password="hunter2")

        captured = capsys.readouterr()
        outerr = captured.out + captured.err
        assert "<redacted>" not in outerr
        assert "hunter2" in outerr
