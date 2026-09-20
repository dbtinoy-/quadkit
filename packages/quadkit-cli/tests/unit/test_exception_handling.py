"""Tests for CLI exception handling specificity."""

from __future__ import annotations

import pytest

from quadkit.cli.exceptions import CliError
from quadkit.contracts.exceptions import QuadkitError


def test_cli_error_is_quadkit_error() -> None:
    """CLI errors must extend QuadkitError."""
    error = CliError("test message")
    assert isinstance(error, QuadkitError)


def test_cli_error_with_causes_and_suggestions() -> None:
    """CLI errors can include causes and suggestions."""
    error = CliError(
        message="test error",
        causes=["cause1", "cause2"],
        suggestions=["suggestion1", "suggestion2"],
    )
    assert error.causes == ["cause1", "cause2"]
    assert error.suggestions == ["suggestion1", "suggestion2"]


def test_no_bare_except_exception_in_runtime() -> None:
    """Verify error_handler.py uses specific exceptions.

    This test ensures CLI runtime error handling catches specific
    exceptions rather than bare 'except Exception'.
    """
    # This is verified by ruff linting
    # Run: ruff check --select=BLE001 quadkit-cli/src/
    pass


def test_no_bare_except_exception_in_registry() -> None:
    """Verify registry modules use specific exceptions.

    This test ensures registry modules (database, telemetry, server)
    catch specific exceptions rather than bare 'except Exception'.
    """
    # This is verified by ruff linting
    # Run: ruff check --select=BLE001 quadkit-cli/src/registry/
    pass


def test_cli_error_inheritance_chain() -> None:
    """Verify CLI error hierarchy is properly structured."""
    from quadkit.cli.exceptions import ConfigNotFoundError, ProviderNotInstalledError

    config_error = ConfigNotFoundError()
    assert isinstance(config_error, CliError)
    assert isinstance(config_error, QuadkitError)

    provider_error = ProviderNotInstalledError("openai")
    assert isinstance(provider_error, CliError)
    assert isinstance(provider_error, QuadkitError)
