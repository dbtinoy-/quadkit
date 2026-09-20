"""Tests for `config validate` command."""

from pathlib import Path

from typer.testing import CliRunner

from quadkit.cli.commands.config import app


class TestConfigValidate:
    def test_config_validate_success(self, tmp_path: Path, monkeypatch):
        """Verify `config validate` succeeds with a valid config."""
        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "application.yaml"
        config_file.write_text("""
project:
  name: test
  version: 0.1.0
logging:
  level: INFO
""")

        result = runner.invoke(app, ["validate"], catch_exceptions=False)

        assert result.exit_code == 0
        assert "Configuration is valid!" in result.stdout

    def test_config_validate_failure(self, tmp_path: Path, monkeypatch):
        """Verify `config validate` fails with an invalid config."""
        runner = CliRunner()
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "application.yaml"
        config_file.write_text("""
project:
  name: test
database:
  url: ""
""")

        result = runner.invoke(app, ["validate"], catch_exceptions=False)

        assert result.exit_code == 1
        assert "Configuration validation failed" in result.stdout
        assert "database.url is required" in result.stdout
