from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from quadkit.cli.commands.contrib import _names_preview


class TestNamesPreview:
    def test_empty(self) -> None:
        result = _names_preview([], "name")
        assert result == ""

    def test_single_item(self) -> None:
        items = [type("obj", (), {"name": "foo"})()]
        result = _names_preview(items, "name")
        assert result == "foo"

    def test_within_limit(self) -> None:
        items = [type("obj", (), {"name": f"item{i}"})() for i in range(3)]
        result = _names_preview(items, "name", limit=5)
        assert "item0" in result
        assert "+" not in result

    def test_exceeds_limit(self) -> None:
        items = [type("obj", (), {"name": f"item{i}"})() for i in range(10)]
        result = _names_preview(items, "name", limit=3)
        assert "+7 more" in result

    def test_missing_attr(self) -> None:
        items = [type("obj", (), {})()]
        result = _names_preview(items, "name")
        assert result == "?"


class TestContribCommand:
    runner = CliRunner()

    @patch("quadkit.cli.commands.contrib.ContributorRuntime.from_entry_points")
    def test_list_no_contributors(self, mock_runtime: MagicMock) -> None:
        mock_runtime.return_value.contributors = []
        mock_runtime.return_value.errors = {}
        mock_runtime.return_value.command_conflicts = {}

        from quadkit.cli.commands.contrib import app as contrib_app
        result = self.runner.invoke(contrib_app, ["list"])
        assert result.exit_code == 0
        assert "No CLI contributors" in result.stdout

    @patch("quadkit.cli.commands.contrib.ContributorRuntime.from_entry_points")
    def test_list_with_core(self, mock_runtime: MagicMock) -> None:
        mock_contrib = MagicMock()
        mock_contrib.contributor_id = "core"
        mock_contrib.get_generators.return_value = []
        mock_contrib.get_commands = lambda: []
        mock_contrib.get_health_checks = lambda: []
        mock_contrib.get_doctor_checks = lambda: []
        mock_contrib.get_shell_context = lambda: []
        mock_contrib.get_hooks = lambda: []

        mock_runtime.return_value.contributors = [mock_contrib]
        mock_runtime.return_value.errors = {}
        mock_runtime.return_value.command_conflicts = {}

        from quadkit.cli.commands.contrib import app as contrib_app
        result = self.runner.invoke(contrib_app, ["list"])
        assert result.exit_code == 0
        assert "core" in result.stdout

    @patch("quadkit.cli.commands.contrib.ContributorRuntime.from_entry_points")
    def test_list_with_errors(self, mock_runtime: MagicMock) -> None:
        mock_error = MagicMock()
        mock_error.contributor_id = "bad_contrib"
        mock_error.exception = "ImportError: something"

        mock_runtime.return_value.contributors = []
        mock_runtime.return_value.errors = {"bad_contrib": mock_error}
        mock_runtime.return_value.command_conflicts = {}

        from quadkit.cli.commands.contrib import app as contrib_app
        result = self.runner.invoke(contrib_app, ["list"])
        assert result.exit_code == 0
        assert "bad_contrib" in result.stdout

    @patch("quadkit.cli.commands.contrib.ContributorRuntime.from_entry_points")
    def test_inspect_not_found(self, mock_runtime: MagicMock) -> None:
        mock_runtime.return_value.contributors = []
        mock_runtime.return_value.errors = {}

        from quadkit.cli.commands.contrib import app as contrib_app
        result = self.runner.invoke(contrib_app, ["inspect", "nonexistent"])
        assert result.exit_code != 0
        assert "not found" in result.stdout

    @patch("quadkit.cli.commands.contrib.ContributorRuntime.from_entry_points")
    def test_inspect_found(self, mock_runtime: MagicMock) -> None:
        mock_contrib = MagicMock()
        mock_contrib.contributor_id = "test"
        mock_contrib.get_generators.return_value = []
        mock_contrib.get_commands = lambda: []
        mock_contrib.get_health_checks = lambda: []
        mock_contrib.get_doctor_checks = lambda: []
        mock_contrib.get_shell_context = lambda: []
        mock_contrib.get_hooks = lambda: []

        mock_runtime.return_value.contributors = [mock_contrib]
        mock_runtime.return_value.errors = {}

        from quadkit.cli.commands.contrib import app as contrib_app
        result = self.runner.invoke(contrib_app, ["inspect", "test"])
        assert result.exit_code == 0
        assert "test" in result.stdout

    @patch("quadkit.cli.commands.contrib.ContributorRuntime.from_entry_points")
    def test_check_healthy(self, mock_runtime: MagicMock) -> None:
        mock_runtime.return_value.contributors = [MagicMock(contributor_id="good")]
        mock_runtime.return_value.errors = {}
        mock_runtime.return_value.command_conflicts = {}

        from quadkit.cli.commands.contrib import app as contrib_app
        result = self.runner.invoke(contrib_app, ["check"])
        assert result.exit_code == 0
        assert "healthy" in result.stdout

    @patch("quadkit.cli.commands.contrib.ContributorRuntime.from_entry_points")
    def test_check_with_errors(self, mock_runtime: MagicMock) -> None:
        mock_error = MagicMock()
        mock_error.contributor_id = "bad"
        mock_error.stage = "load"
        mock_error.exception = "fail"

        mock_runtime.return_value.contributors = []
        mock_runtime.return_value.errors = {"bad": mock_error}
        mock_runtime.return_value.command_conflicts = {}

        from quadkit.cli.commands.contrib import app as contrib_app
        result = self.runner.invoke(contrib_app, ["check"])
        assert result.exit_code != 0
