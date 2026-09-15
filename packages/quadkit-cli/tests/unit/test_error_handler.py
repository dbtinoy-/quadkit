"""Tests for the CLI error handler decorator."""

import pytest
from typer.testing import CliRunner
import typer

from quadkit.cli.runtime import handle_errors
from quadkit.cli.exceptions import CliError, ConfigNotFoundError


class TestErrorHandler:
    def test_passes_through_on_success(self):
        test_app = typer.Typer()

        @test_app.command()
        @handle_errors
        def good_cmd():
            print("ok")  # noqa: T201

        runner = CliRunner()
        result = runner.invoke(test_app, [])
        assert result.exit_code == 0
        assert "ok" in result.output

    def test_catches_cli_error(self):
        test_app = typer.Typer()

        @test_app.command()
        @handle_errors
        def bad_cmd():
            raise CliError("something broke", suggestions=["try again"])

        runner = CliRunner()
        result = runner.invoke(test_app, [])
        assert result.exit_code == 1
        assert "something broke" in result.output
        assert "try again" in result.output

    def test_catches_config_not_found(self):
        test_app = typer.Typer()

        @test_app.command()
        @handle_errors
        def cfg_cmd():
            raise ConfigNotFoundError()

        runner = CliRunner()
        result = runner.invoke(test_app, [])
        assert result.exit_code == 1
        assert "application.yaml" in result.output

    def test_unexpected_error_shows_traceback_in_debug(self):
        test_app = typer.Typer()

        @test_app.command()
        @handle_errors
        def crash_cmd():
            raise RuntimeError("unexpected")

        runner = CliRunner()
        result = runner.invoke(test_app, [])
        assert result.exit_code == 1
        assert "unexpected" in result.output
