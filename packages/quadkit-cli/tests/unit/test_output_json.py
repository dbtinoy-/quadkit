"""Tests for OutputManager JSON mode and @handle_errors decorator rendering."""

from __future__ import annotations

from io import StringIO

from quadkit import serialization as json
from unittest.mock import patch

import pytest
import typer

from quadkit.cli.exceptions import CliError
from quadkit.cli.output.manager import OutputManager
from quadkit.cli.runtime.error_handler import handle_errors


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _capture_json_output(fn, *args, **kwargs) -> dict:
    """Call fn (which uses print() in json mode) and parse the stdout."""
    buf = StringIO()
    with patch("builtins.print", side_effect=lambda s: buf.write(s + "\n")):
        fn(*args, **kwargs)
    return json.loads(buf.getvalue().strip())


class TestOutputManagerJsonMode:
    """OutputManager.json_mode=True must emit valid JSON for every method."""

    def test_success_emits_status_success(self) -> None:
        out = OutputManager(json_mode=True)
        result = _capture_json_output(out.success, "Done")
        assert result["status"] == "success"
        assert result["message"] == "Done"

    def test_success_with_data_includes_data_key(self) -> None:
        out = OutputManager(json_mode=True)
        result = _capture_json_output(out.success, "Created", {"id": "abc123"})
        assert result["data"]["id"] == "abc123"

    def test_success_without_data_omits_data_key(self) -> None:
        out = OutputManager(json_mode=True)
        result = _capture_json_output(out.success, "OK")
        assert "data" not in result

    def test_error_emits_status_error(self) -> None:
        out = OutputManager(json_mode=True)
        result = _capture_json_output(out.error, "Something broke")
        assert result["status"] == "error"
        assert result["message"] == "Something broke"

    def test_error_with_hint_includes_hint(self) -> None:
        out = OutputManager(json_mode=True)
        result = _capture_json_output(out.error, "Oops", "Try restarting")
        assert result["hint"] == "Try restarting"

    def test_error_without_hint_omits_hint(self) -> None:
        out = OutputManager(json_mode=True)
        result = _capture_json_output(out.error, "Fail")
        assert "hint" not in result

    def test_warning_emits_status_warning(self) -> None:
        out = OutputManager(json_mode=True)
        result = _capture_json_output(out.warning, "Careful")
        assert result["status"] == "warning"
        assert result["message"] == "Careful"

    def test_table_emits_list_of_dicts(self) -> None:
        out = OutputManager(json_mode=True)
        result = _capture_json_output(
            out.table, ["name", "version"], [["uvicorn", "0.30"], ["pydantic", "2.0"]]
        )
        assert isinstance(result, list)
        assert result[0]["name"] == "uvicorn"
        assert result[1]["version"] == "2.0"

    def test_key_value_emits_dict(self) -> None:
        out = OutputManager(json_mode=True)
        result = _capture_json_output(out.key_value, {"host": "localhost", "port": 8000})
        assert result["host"] == "localhost"
        assert result["port"] == 8000

    def test_cli_error_emits_full_error_payload(self) -> None:
        out = OutputManager(json_mode=True)
        err = CliError(
            message="Config not found",
            causes=["File deleted"],
            suggestions=["Run init"],
        )
        result = _capture_json_output(out.cli_error, err)
        assert result["status"] == "error"
        assert result["message"] == "Config not found"
        assert "File deleted" in result["causes"]
        assert "Run init" in result["suggestions"]

    def test_info_produces_no_output_in_json_mode(self) -> None:
        out = OutputManager(json_mode=True)
        printed: list[str] = []
        with patch("builtins.print", side_effect=printed.append):
            out.info("Informational message")
        assert printed == []

    def test_success_in_quiet_mode_produces_no_output(self) -> None:
        out = OutputManager(quiet=True)
        printed: list[str] = []
        with patch("builtins.print", side_effect=printed.append):
            out.success("Silent")
        assert printed == []


class TestHandleErrorsDecorator:
    """@handle_errors renders CliError and unexpected errors and exits(1)."""

    def test_cli_error_calls_cli_error_and_exits(self) -> None:
        err = CliError("bad config", causes=["missing file"], suggestions=["run init"])

        @handle_errors
        def failing_command() -> None:
            raise err

        rendered: list[CliError] = []
        with patch.object(OutputManager, "cli_error", side_effect=rendered.append):
            with pytest.raises(typer.Exit) as exc_info:
                failing_command()

        assert exc_info.value.exit_code == 1
        assert rendered[0] is err

    def test_unexpected_exception_calls_error_and_exits(self) -> None:
        @handle_errors
        def boom() -> None:
            raise RuntimeError("unexpected crash")

        errors: list[str] = []
        with patch.object(
            OutputManager, "error", side_effect=lambda msg, hint=None: errors.append(msg)
        ):
            with pytest.raises(typer.Exit) as exc_info:
                boom()

        assert exc_info.value.exit_code == 1
        assert "unexpected crash" in errors[0]

    def test_typer_exit_passes_through(self) -> None:
        @handle_errors
        def command() -> None:
            raise typer.Exit(0)

        with pytest.raises(typer.Exit) as exc_info:
            command()

        assert exc_info.value.exit_code == 0

    def test_successful_command_returns_normally(self) -> None:
        @handle_errors
        def ok_command() -> str:
            return "result"

        assert ok_command() == "result"

    def test_cli_error_with_causes_rendered_in_json_mode(self) -> None:
        """JSON mode should include causes and suggestions in the error payload."""
        err = CliError(
            message="Deployment failed",
            causes=["Network timeout"],
            suggestions=["Check connectivity"],
        )
        out = OutputManager(json_mode=True)
        result = _capture_json_output(out.cli_error, err)
        assert result["causes"] == ["Network timeout"]
        assert result["suggestions"] == ["Check connectivity"]
