"""Tests for the cache CLI command group factory."""

from __future__ import annotations

from typer.testing import CliRunner

from quadkit.cache.cli.commands import create_cache_app

runner = CliRunner()


def _app():
    return create_cache_app()


def _registered_commands():
    app = _app()
    return {cmd.name for cmd in app.registered_commands}


class TestCommandGroup:
    def test_all_commands_registered(self) -> None:
        assert _registered_commands() == {"status", "flush", "keys", "get", "stats"}

    def test_help_available(self) -> None:
        result = runner.invoke(_app(), ["--help"])
        assert result.exit_code == 0
        assert "Cache inspection and management" in result.output


class TestCommandsAreHonestPlaceholders:
    """All five commands are placeholders; each must announce that
    explicitly rather than silently no-op (docstring + output agree)."""

    def test_status_placeholder(self) -> None:
        result = runner.invoke(_app(), ["status"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output

    def test_flush_placeholder(self) -> None:
        result = runner.invoke(_app(), ["flush", "--pattern", "x:*", "--force"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output

    def test_keys_placeholder(self) -> None:
        result = runner.invoke(_app(), ["keys", "--pattern", "*", "--limit", "5"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output

    def test_get_placeholder_requires_key(self) -> None:
        # Missing required argument → usage error.
        result = runner.invoke(_app(), ["get"])
        assert result.exit_code != 0

    def test_get_placeholder(self) -> None:
        result = runner.invoke(_app(), ["get", "my:key"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output
        assert "my:key" in result.output

    def test_stats_placeholder(self) -> None:
        result = runner.invoke(_app(), ["stats"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.output
