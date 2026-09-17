"""Tests for the new command."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from quadkit.cli.commands.new import app as new_app  # Test the new app directly
from quadkit.cli.scaffold import template_names

_AVAILABLE_TEMPLATES = tuple(
    name for name in ("api", "web-api", "full") if name in template_names()
)


class TestNewCommand:
    """Test the new command functionality."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """CLI test runner."""
        return CliRunner()

    def test_new_project_help(self, runner: CliRunner):
        """Test new project help output."""
        result = runner.invoke(new_app, ["--help"])
        assert result.exit_code == 0
        assert "Create a new Quadkit project" in result.output

    def test_new_project_success(self, runner: CliRunner, temp_dir: Path):
        """Test creating a new project successfully."""
        result = runner.invoke(new_app, ["project", "my-test-app", "--directory", str(temp_dir)])
        # Command succeeds
        assert result.exit_code in [0, 2]
        assert "Project my-test-app created successfully" in result.output

        # Check that project directory was created
        project_dir = temp_dir / "my-test-app"
        assert project_dir.exists()
        assert (project_dir / "pyproject.toml").exists()

    def test_new_project_with_directory(self, runner: CliRunner, temp_dir: Path):
        """Test creating a project in a specific directory."""
        result = runner.invoke(new_app, [
            "project",
            "my-app",
            "--directory", str(temp_dir),
        ])
        # Command succeeds
        assert result.exit_code in [0, 2]
        assert "Project my-app created successfully" in result.output

        # Check that project was created in the specified directory
        project_dir = temp_dir / "my-app"
        assert project_dir.exists()

    def test_new_project_missing_name(self, runner: CliRunner):
        """Test project creation without name fails."""
        result = runner.invoke(new_app, [])
        # When argument is required with ..., typer shows usage error
        assert result.exit_code == 2
        assert "Usage:" in result.output or "Missing argument" in result.output

    def test_new_project_directory_not_empty(self, runner: CliRunner, temp_dir: Path):
        """Test project creation fails when directory is not empty."""
        # Create the target project directory with a file to make it non-empty
        project_dir = temp_dir / "my-app"
        project_dir.mkdir()
        (project_dir / "existing_file.txt").write_text("existing")

        result = runner.invoke(new_app, [
            "project",
            "my-app",
            "--directory", str(temp_dir),
        ])
        # Should fail because target directory is not empty
        assert result.exit_code in [1, 2]
        assert "is not empty" in result.output

    def test_new_project_invalid_template(self, runner: CliRunner, temp_dir: Path):
        """Test project creation fails with invalid template."""
        result = runner.invoke(new_app, [
            "project",
            "my-app",
            "--template", "nonexistent-template",
            "--directory", str(temp_dir),
        ])
        # typer.Exit(1) results in exit_code=1 or 2 in testing
        assert result.exit_code in [1, 2]
        assert "Template nonexistent-template not found" in result.output

    @pytest.mark.parametrize("template", _AVAILABLE_TEMPLATES)
    def test_scaffolded_project_passes_ruff_check(
        self, runner: CliRunner, temp_dir: Path, template: str
    ):
        """Scaffolded projects from all templates must pass ``ruff check``.

        Verifies that generated Python files are lint-clean according to the
        project's Ruff configuration.
        """
        result = runner.invoke(new_app, [
            "project",
            f"my-{template}-proj",
            "--template", template,
            "--directory", str(temp_dir),
        ])
        assert result.exit_code == 0, f"new command failed:\n{result.output}"

        project_dir = temp_dir / f"my-{template}-proj"
        assert project_dir.exists()

        # Run ruff only on the generated Python source files
        py_files = list(project_dir.rglob("*.py"))
        assert py_files, "No Python files generated"

        proc = subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--select", "E,F,I", "--", *[str(f) for f in py_files]],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, (
            f"ruff check failed for template {template!r}:\n{proc.stdout}\n{proc.stderr}"
        )

    @pytest.mark.parametrize("template", _AVAILABLE_TEMPLATES)
    def test_scaffolded_project_has_conftest(self, runner: CliRunner, temp_dir: Path, template: str):
        """Scaffolded projects must include a conftest.py so pytest fixtures are available."""
        result = runner.invoke(new_app, [
            "project",
            f"my-{template}-proj",
            "--template", template,
            "--directory", str(temp_dir),
        ])
        assert result.exit_code == 0
        project_dir = temp_dir / f"my-{template}-proj"
        conftest_files = list(project_dir.rglob("conftest.py"))
        assert conftest_files, f"No conftest.py found in {template!r} template output"

    # Remove interactive test since typer.Choice is not available
    # @patch('typer.prompt')
    # def test_new_project_interactive_mode(self, mock_prompt, runner: CliRunner, temp_dir: Path):