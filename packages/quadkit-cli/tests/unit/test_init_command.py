"""Tests for `quadkit init` command."""

from pathlib import Path

from typer.testing import CliRunner

from quadkit.cli.commands.init import app


class TestInitCommand:
    def setup_method(self):
        self.runner = CliRunner()

    def test_init_creates_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = self.runner.invoke(app, [])
        assert result.exit_code == 0
        assert (tmp_path / "application.yaml").exists()

    def test_init_minimal(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = self.runner.invoke(app, ["--minimal"])
        assert result.exit_code == 0
        content = (tmp_path / "application.yaml").read_text()
        assert "app_name:" in content
        # Minimal should be short
        assert len(content.splitlines()) < 20

    def test_init_full(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = self.runner.invoke(app, ["--full"])
        assert result.exit_code == 0
        content = (tmp_path / "application.yaml").read_text()
        assert "sql:" in content
        assert "web:" in content

    def test_init_refuses_overwrite(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "application.yaml").write_text("existing config")
        result = self.runner.invoke(app, [])
        assert result.exit_code == 1
        assert "already exists" in result.output

    def test_init_force_overwrite(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "application.yaml").write_text("existing config")
        result = self.runner.invoke(app, ["--force"])
        assert result.exit_code == 0
