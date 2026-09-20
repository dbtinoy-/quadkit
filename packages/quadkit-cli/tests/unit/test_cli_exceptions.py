"""Tests for CLI exceptions."""

import pytest

from quadkit.cli.exceptions import (
    CliError,
    ConfigNotFoundError,
    ProviderNotInstalledError,
)


class TestCliError:
    """Tests for CliError base class."""

    def test_cli_error_basic(self) -> None:
        """Should instantiate with message."""
        error = CliError("CLI error occurred")
        assert "CLI error occurred" in str(error)

    def test_cli_error_with_causes(self) -> None:
        """Should support causes."""
        error = CliError("Error", causes=["Cause 1", "Cause 2"])
        assert len(error.causes) == 2
        assert "Cause 1" in error.causes

    def test_cli_error_with_suggestions(self) -> None:
        """Should support suggestions."""
        error = CliError("Error", suggestions=["Fix it", "Try again"])
        assert len(error.suggestions) == 2
        assert "Fix it" in error.suggestions

    def test_cli_error_defaults(self) -> None:
        """Should have empty defaults."""
        error = CliError("Error")
        assert error.causes == []
        assert error.suggestions == []


class TestConfigNotFoundError:
    """Tests for ConfigNotFoundError."""

    def test_config_not_found_error(self) -> None:
        """Should instantiate with default message."""
        error = ConfigNotFoundError()
        assert "application.yaml" in str(error)
        assert len(error.suggestions) > 0


class TestProviderNotInstalledError:
    """Tests for ProviderNotInstalledError."""

    def test_provider_not_installed_error(self) -> None:
        """Should instantiate with provider name."""
        error = ProviderNotInstalledError("database")
        assert "database" in str(error)
        assert len(error.suggestions) > 0
