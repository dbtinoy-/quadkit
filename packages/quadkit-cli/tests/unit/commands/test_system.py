from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from quadkit.cli.commands.system import _resolve_callable


class TestResolveCallable:
    def test_resolve_valid_path(self) -> None:
        fn = _resolve_callable("pathlib:Path")
        assert fn is Path

    def test_resolve_invalid_path(self) -> None:
        with pytest.raises(ValueError):
            _resolve_callable("")

    def test_resolve_bad_module(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            _resolve_callable("nonexistent_module:anything")


class TestSystemCommand:
    runner = CliRunner()

    @patch("quadkit.cli.commands.system.Path.exists", return_value=False)
    def test_info(self, mock_exists: MagicMock) -> None:
        from quadkit.cli.commands.system import app as system_app
        result = self.runner.invoke(system_app, ["info"])
        assert result.exit_code == 0
        assert "Python Version" in result.stdout

    @patch("quadkit.cli.commands.system.Path.exists", return_value=True)
    def test_info_with_config(self, mock_exists: MagicMock) -> None:
        from quadkit.cli.commands.system import app as system_app
        result = self.runner.invoke(system_app, ["info"])
        assert result.exit_code == 0
        assert "Project Config" in result.stdout

    @patch("quadkit.cli.commands.system.run_health_checks", return_value={})
    @patch("quadkit.cli.contributors.runtime.ContributorRuntime")
    def test_doctor(self, mock_runtime_cls: MagicMock, mock_checks: MagicMock) -> None:
        mock_runtime = MagicMock()
        mock_runtime.doctor_checks = []
        mock_runtime_cls.from_entry_points.return_value = mock_runtime
        from quadkit.cli.commands.system import app as system_app
        with patch("quadkit.cli.commands.system.Path.exists", return_value=False):
            result = self.runner.invoke(system_app, ["doctor"])
        assert result.exit_code == 0

    @patch("quadkit.cli.commands.system.console")
    @patch("code.interact")
    def test_shell(self, mock_interact: MagicMock, mock_console: MagicMock) -> None:
        from quadkit.cli.commands.system import app as system_app
        result = self.runner.invoke(system_app, ["shell"])
        assert result.exit_code == 0

    @patch("quadkit.cli.commands.system.console")
    @patch("quadkit.cli.commands.system.Path.exists", return_value=False)
    def test_providers_no_config(
        self, mock_exists: MagicMock, mock_console: MagicMock
    ) -> None:
        from quadkit.cli.commands.system import app as system_app
        result = self.runner.invoke(system_app, ["providers"])
        assert result.exit_code == 0

    @patch("quadkit.cli.commands.system.console")
    def test_providers_with_config(self, mock_console: MagicMock) -> None:
        from unittest.mock import mock_open as mock_open_factory
        from quadkit.cli.commands.system import app as system_app
        with (
            patch("quadkit.cli.commands.system.Path.exists", return_value=True),
            patch("builtins.open", mock_open_factory(read_data="database:\n  url: sqlite:///dev.db")),
        ):
            result = self.runner.invoke(system_app, ["providers"])
            assert result.exit_code == 0

    @patch("quadkit.cli.commands.system.Path.exists", return_value=True)
    def test_health_no_project(self, mock_exists: MagicMock) -> None:
        from quadkit.cli.commands.system import app as system_app

        with (
            patch("quadkit.cli.commands.system.run_health_checks", return_value={}),
            patch(
                "quadkit.cli.contributors.runtime.ContributorRuntime",
            ) as mock_runtime_cls,
        ):
            mock_runtime = MagicMock()
            mock_runtime.health_checks = []
            mock_runtime_cls.from_entry_points.return_value = mock_runtime
            result = self.runner.invoke(system_app, ["health"])
            assert result.exit_code == 0
