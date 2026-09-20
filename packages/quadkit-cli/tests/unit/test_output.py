"""Tests for OutputManager."""

from quadkit import serialization as json

from quadkit.cli.output import OutputManager


class TestOutputManagerDefault:
    """Test default (Rich) output mode."""

    def test_success_message(self, capsys):
        out = OutputManager()
        out.success("Operation completed")
        # Rich writes to its own console, check it doesn't crash
        # and the message is produced
        assert out.json_mode is False

    def test_error_message(self, capsys):
        out = OutputManager()
        out.error("Something failed", hint="Try again")
        assert out.json_mode is False


class TestOutputManagerJson:
    """Test JSON output mode."""

    def test_success_json(self, capsys):
        out = OutputManager(json_mode=True)
        out.success("done", data={"count": 5})
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["status"] == "success"
        assert parsed["message"] == "done"
        assert parsed["data"]["count"] == 5

    def test_error_json(self, capsys):
        out = OutputManager(json_mode=True)
        out.error("failed", hint="check logs")
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["status"] == "error"
        assert parsed["hint"] == "check logs"

    def test_table_json(self, capsys):
        out = OutputManager(json_mode=True)
        out.table(["Name", "Status"], [["db", "healthy"], ["cache", "degraded"]])
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert len(parsed) == 2
        assert parsed[0]["Name"] == "db"

    def test_key_value_json(self, capsys):
        out = OutputManager(json_mode=True)
        out.key_value({"version": "0.1.1", "python": "3.12"})
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["version"] == "0.1.1"


class TestOutputManagerQuiet:
    """Test quiet mode — only errors should produce output."""

    def test_success_suppressed(self, capsys):
        out = OutputManager(quiet=True)
        out.success("this should not appear")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_error_still_shown(self, capsys):
        out = OutputManager(quiet=True)
        out.error("this should appear")
        captured = capsys.readouterr()
        assert "this should appear" in captured.out


class TestOutputManagerCliError:
    """Test rendering of CLIError objects."""

    def test_render_cli_error(self, capsys):
        from quadkit.cli.exceptions import CliError
        err = CliError(
            "Connection refused",
            causes=["DB not running"],
            suggestions=["Start the database"],
        )
        out = OutputManager()
        out.cli_error(err)
        # Should not raise

    def test_render_cli_error_json(self, capsys):
        from quadkit.cli.exceptions import CliError
        err = CliError("bad", causes=["reason"], suggestions=["fix it"])
        out = OutputManager(json_mode=True)
        out.cli_error(err)
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["status"] == "error"
        assert parsed["causes"] == ["reason"]
