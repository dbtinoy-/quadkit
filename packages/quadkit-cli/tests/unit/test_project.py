"""Tests for the project command."""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from quadkit.cli.commands.project import app


class TestProjectCommand:
    """Test the project command functionality."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """CLI test runner."""
        return CliRunner()

    def test_project_help(self, runner: CliRunner):
        """Test project help output."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Run project tests" in result.output

    @patch("quadkit.cli.commands.project._runner_registry")
    def test_project_test_success(self, mock_registry, runner: CliRunner):
        """Test project test command success."""
        mock_runner = MagicMock()
        mock_runner.is_available.return_value = True
        mock_runner.run.return_value = MagicMock(success=True, output="Tests passed", exit_code=0)
        mock_registry.return_value.get.return_value = mock_runner
        mock_registry.return_value.get_all.return_value = {"pytest": mock_runner}

        result = runner.invoke(app, ["test", "--coverage"])
        assert result.exit_code == 0
        assert "Tests passed" in result.output
        mock_runner.run.assert_called_once()
        # Verify coverage flag was passed to run method
        args, kwargs = mock_runner.run.call_args
        assert kwargs.get("coverage") is True

    @patch("quadkit.cli.commands.project._runner_registry")
    def test_project_test_failure(self, mock_registry, runner: CliRunner):
        """Test project test command failure."""
        mock_runner = MagicMock()
        mock_runner.is_available.return_value = True
        mock_runner.run.return_value = MagicMock(success=False, output="Tests failed", exit_code=1)
        mock_registry.return_value.get.return_value = mock_runner

        result = runner.invoke(app, ["test"])
        assert result.exit_code == 1
        assert "Tests failed" in result.output

    @patch("quadkit.cli.commands.project._runner_registry")
    def test_project_lint_success(self, mock_registry, runner: CliRunner):
        """Test project lint command success."""
        mock_runner = MagicMock()
        mock_runner.is_available.return_value = True
        mock_runner.run.return_value = MagicMock(success=True, output="Linting passed", exit_code=0)
        mock_registry.return_value.get.return_value = mock_runner

        result = runner.invoke(app, ["lint", "--fix"])
        assert result.exit_code == 0
        assert "Linting passed" in result.output
        mock_runner.run.assert_called_once()
        args, kwargs = mock_runner.run.call_args
        assert kwargs.get("fix") is True

    @patch("quadkit.cli.commands.project._runner_registry")
    def test_project_typecheck_success(self, mock_registry, runner: CliRunner):
        """Test project typecheck command success."""
        mock_runner = MagicMock()
        mock_runner.is_available.return_value = True
        mock_runner.run.return_value = MagicMock(success=True, output="Type checking passed", exit_code=0)
        mock_registry.return_value.get.return_value = mock_runner

        result = runner.invoke(app, ["typecheck", "src/myapp"])
        assert result.exit_code == 0
        assert "Type checking passed" in result.output
        mock_runner.run.assert_called_once()
        args, kwargs = mock_runner.run.call_args
        assert kwargs.get("path") == "src/myapp"

    def test_project_routes_discovery(self, runner: CliRunner):
        """Test project routes command (mock output)."""
        result = runner.invoke(app, ["routes", "--app", "myapp.main:app"])
        assert result.exit_code == 0
        assert "Route introspection is not yet implemented" in result.output

    @patch("quadkit.cli.commands.project._runner_registry")
    def test_project_run_all_success(self, mock_registry, runner: CliRunner):
        """Test project run-all command success."""
        mock_runner = MagicMock()
        mock_runner.is_available.return_value = True
        mock_runner.run.return_value = MagicMock(success=True, output="Passed", exit_code=0)
        mock_registry.return_value.get.return_value = mock_runner

        result = runner.invoke(app, ["run-all"])
        assert result.exit_code == 0
        assert "All checks passed!" in result.output
        assert mock_runner.run.call_count == 3  # pytest, ruff, mypy
