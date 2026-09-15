from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from quadkit.cli.commands.meta import (
    _build_command_registry,
    completion,
    list_commands,
    version,
)


class TestMetaVersion:
    @patch("quadkit.cli.commands.meta.OutputManager")
    def test_version_simple(self, mock_out: MagicMock) -> None:
        from quadkit.cli.constants import __version__
        version(all_packages=False)
        mock_out.return_value.print.assert_called_once_with(f"quadkit {__version__}")

    @patch("quadkit.cli.commands.meta.OutputManager")
    def test_version_all_packages(self, mock_out: MagicMock) -> None:
        with patch("importlib.metadata.version") as mock_metadata:
            mock_metadata.side_effect = lambda pkg: {"quadkit": "0.1.0"}.get(pkg, "1.0.0")
            version(all_packages=True)
        mock_out.return_value.table.assert_called_once()

    @patch("quadkit.cli.commands.meta.OutputManager")
    def test_version_all_packages_not_installed(self, mock_out: MagicMock) -> None:
        import importlib.metadata
        with patch("importlib.metadata.version", side_effect=importlib.metadata.PackageNotFoundError):
            version(all_packages=True)
        mock_out.return_value.table.assert_called_once()


class TestMetaCompletion:
    @patch("quadkit.cli.commands.meta.OutputManager")
    def test_completion_bash(self, mock_out: MagicMock) -> None:
        completion(shell="bash")
        calls = mock_out.return_value.print.call_args_list
        assert any("bash" in str(c) for c in calls)

    @patch("quadkit.cli.commands.meta.OutputManager")
    def test_completion_zsh(self, mock_out: MagicMock) -> None:
        completion(shell="zsh")
        calls = mock_out.return_value.print.call_args_list
        assert any("zsh" in str(c) for c in calls)

    @patch("quadkit.cli.commands.meta.OutputManager")
    def test_completion_fish(self, mock_out: MagicMock) -> None:
        completion(shell="fish")
        calls = mock_out.return_value.print.call_args_list
        assert any("fish" in str(c) for c in calls)

    @patch("quadkit.cli.commands.meta.OutputManager")
    def test_completion_powershell(self, mock_out: MagicMock) -> None:
        completion(shell="powershell")
        calls = mock_out.return_value.print.call_args_list
        assert any("PowerShell" in str(c) for c in calls)

    @patch("quadkit.cli.commands.meta.OutputManager")
    def test_completion_unsupported_shell(self, mock_out: MagicMock) -> None:
        import typer
        with pytest.raises(typer.Exit):
            completion(shell="unknown_shell")
        mock_out.return_value.error.assert_called_once()


class TestMetaListCommands:
    @patch("quadkit.cli.commands.meta.OutputManager")
    def test_list_commands_default(self, mock_out: MagicMock) -> None:
        list_commands()
        assert mock_out.return_value.print.call_count >= 1

    @patch("quadkit.cli.commands.meta.OutputManager")
    def test_list_commands_json(self, mock_out: MagicMock) -> None:
        with patch("quadkit.serialization.dumps_str") as mock_dumps:
            list_commands(json_output=True)
        mock_out.return_value.print.assert_called_once()

    @patch("quadkit.cli.commands.meta.OutputManager")
    def test_list_commands_unknown_group(self, mock_out: MagicMock) -> None:
        list_commands(group="nonexistent")
        mock_out.return_value.error.assert_called_once()


class TestBuildCommandRegistry:
    def test_registry_contains_builtins(self) -> None:
        registry = _build_command_registry()
        names = registry.names()
        assert "init" in names
        assert "run" in names
        assert "db" in names
        assert "config" in names
        assert "version" in names

    def test_registry_all_entries(self) -> None:
        registry = _build_command_registry()
        entries = registry.all_entries()
        assert len(entries) >= 19


import pytest
