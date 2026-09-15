"""Tests for the add command."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from quadkit.cli.commands.add import app


class TestAddCommand:
    """Test the add command functionality."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        """CLI test runner."""
        return CliRunner()

    def test_add_unknown_provider(self, runner: CliRunner):
        """Test adding an unknown provider."""
        result = runner.invoke(app, ["unknown"])
        assert result.exit_code == 1
        assert "Unknown provider: unknown" in result.output
        assert "Available providers:" in result.output

    def test_add_database_provider(self, runner: CliRunner, temp_project: Path):
        """Test adding database provider."""
        result = runner.invoke(app, ["database"])
        assert result.exit_code == 0
        assert "Adding provider database" in result.output
        assert "quadkit-sql" in result.output

        # Check if pyproject.toml was updated (simulated)
        assert "database section" in result.output

        # Check if application.yaml was updated
        quadkit_yaml = temp_project / "application.yaml"
        content = quadkit_yaml.read_text()
        assert "database:" in content

    def test_add_auth_provider(self, runner: CliRunner, temp_project: Path):
        """Test adding auth provider."""
        result = runner.invoke(app, ["auth"])
        assert result.exit_code == 0
        assert "Adding provider auth" in result.output
        assert "quadkit-auth" in result.output

        # Check if application.yaml was updated
        quadkit_yaml = temp_project / "application.yaml"
        content = quadkit_yaml.read_text()
        assert "auth:" in content
        assert "your-secure-secret-key-here" in content

    def test_add_ai_provider(self, runner: CliRunner, temp_project: Path):
        """Test adding AI provider."""
        result = runner.invoke(app, ["ai"])
        assert result.exit_code == 0
        assert "Adding provider ai" in result.output
        assert "quadkit-ai" in result.output

        # Check if application.yaml was updated
        quadkit_yaml = temp_project / "application.yaml"
        content = quadkit_yaml.read_text()
        assert "ai:" in content
        assert "ollama" in content

    def test_add_cache_provider(self, runner: CliRunner, temp_project: Path):
        """Test adding cache provider."""
        result = runner.invoke(app, ["cache"])
        assert result.exit_code == 0
        assert "Adding provider cache" in result.output
        assert "quadkit-cache" in result.output

        # Check if application.yaml was updated
        quadkit_yaml = temp_project / "application.yaml"
        content = quadkit_yaml.read_text()
        assert "cache:" in content
        assert "memory" in content

    def test_add_queue_provider(self, runner: CliRunner, temp_project: Path):
        """Test adding queue provider."""
        result = runner.invoke(app, ["queue"])
        assert result.exit_code == 0
        assert "Adding provider queue" in result.output
        assert "quadkit-queue" in result.output

        # Check if application.yaml was updated
        quadkit_yaml = temp_project / "application.yaml"
        content = quadkit_yaml.read_text()
        assert "queue:" in content
        assert "redis://localhost:6379/0" in content

    def test_add_provider_existing_config(self, runner: CliRunner, temp_project: Path):
        """Test adding provider when config section already exists."""
        # First add database
        runner.invoke(app, ["database"])

        # Try to add it again
        result = runner.invoke(app, ["database"])
        assert result.exit_code == 0
        assert "database section already exists" in result.output

    def test_add_provider_no_pyproject(self, runner: CliRunner, temp_dir: Path):
        """Test adding provider without pyproject.toml."""
        # Change to directory without pyproject.toml
        import os
        original_cwd = os.getcwd()
        os.chdir(temp_dir)
        try:
            result = runner.invoke(app, ["database"])
            assert result.exit_code == 0
            assert "pyproject.toml not found" in result.output
        finally:
            os.chdir(original_cwd)

    def test_add_provider_no_quadkit_yaml(self, runner: CliRunner, temp_dir: Path):
        """Test adding provider without application.yaml."""
        # Create directory with pyproject.toml but no application.yaml
        project_dir = temp_dir / "project"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text("[project]\nname = 'test'")

        import os
        original_cwd = os.getcwd()
        os.chdir(project_dir)
        try:
            result = runner.invoke(app, ["database"])
            assert result.exit_code == 0
            assert "application.yaml not found" in result.output
        finally:
            os.chdir(original_cwd)