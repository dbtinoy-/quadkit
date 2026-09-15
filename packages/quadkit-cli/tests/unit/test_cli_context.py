"""Tests for CLIContext and global flags."""

from typer.testing import CliRunner

from quadkit.cli.runtime import CLIContext


class TestCLIContext:
    def test_default_context(self):
        ctx = CLIContext()
        assert ctx.json_mode is False
        assert ctx.quiet is False
        assert ctx.debug is False
        assert ctx.output is not None

    def test_json_mode_context(self):
        ctx = CLIContext(json_mode=True)
        assert ctx.output.json_mode is True

    def test_config_loaded_lazily(self, tmp_path):
        config_file = tmp_path / "application.yaml"
        config_file.write_text("project:\n  name: test\n")
        ctx = CLIContext(config_path=config_file)
        data = ctx.config_data
        assert data["project"]["name"] == "test"


class TestGlobalFlags:
    def test_version_command(self):
        from quadkit.cli.runtime.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "0.1" in result.output

    def test_version_all(self):
        from quadkit.cli.runtime.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["version", "--all"])
        assert result.exit_code == 0
        assert "quadkit-security" not in result.output

    def test_help_flag(self):
        from quadkit.cli.runtime.main import app
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Quadkit" in result.output
