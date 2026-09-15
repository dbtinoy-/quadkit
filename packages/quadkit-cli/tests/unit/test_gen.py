"""Tests for the gen command."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner


class TestGenCommand:
    """Test the gen command functionality."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """CLI test runner."""
        return CliRunner()

    def test_gen_controller_help(
        self,
        runner: CliRunner,
        gen_app_with_web_generators,
    ) -> None:
        """Test gen controller help output."""
        result = runner.invoke(gen_app_with_web_generators, ["controller", "--help"])
        assert result.exit_code == 0
        assert "controller" in result.output.lower()

    def test_gen_list_help(
        self, runner: CliRunner, gen_app_with_core_generators
    ) -> None:
        """Test gen list help output."""
        result = runner.invoke(gen_app_with_core_generators, ["list", "--help"])
        assert result.exit_code == 0
        assert "list" in result.output.lower()

    def test_gen_list_templates(
        self,
        runner: CliRunner,
        gen_app_with_web_generators,
    ) -> None:
        """Test listing available generators."""
        result = runner.invoke(gen_app_with_web_generators, ["list"])
        assert result.exit_code == 0
        assert "Available generators:" in result.output
        assert "  controller - Generate a web controller with route handlers" in result.output
