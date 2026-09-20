"""Tests for the main CLI entry point."""

import pytest
from typer.testing import CliRunner

from quadkit.cli.constants import __version__ as cli_version
from quadkit.cli.runtime.main import app


class TestMainCLI:
    """Test the main CLI application."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """CLI test runner."""
        return CliRunner()

    def test_main_help(self, runner: CliRunner):
        """Test main help command."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Quadkit Framework CLI" in result.output
        assert "new" in result.output
        assert "add" in result.output
        assert "dev" in result.output

    def test_main_version(self, runner: CliRunner):
        """Test version command."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "quadkit" in result.output
        assert cli_version in result.output

    def test_main_no_args(self, runner: CliRunner):
        """Bare invocation prints full help and exits 0."""
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        # rich_markup_mode renders boxed section headers, so assert on the
        # usage line and a known command rather than a plain "Commands:" line
        assert "Usage: quadkit" in result.output
        assert "new" in result.output

    def test_main_unknown_command(self, runner: CliRunner):
        """Test unknown command."""
        result = runner.invoke(app, ["unknown"])
        assert result.exit_code == 2  # Typer error code for unknown command
        assert "No such command" in result.output
