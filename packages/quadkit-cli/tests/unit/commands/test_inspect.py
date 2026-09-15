from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from quadkit.cli.commands.inspect import _print_needs_context


class TestPrintNeedsContext:
    def test_prints_message(self) -> None:
        mock_out = MagicMock()
        _print_needs_context(mock_out, "inspect modules", "Shows all modules")
        mock_out.print.assert_called()


class TestInspectCommand:
    runner = CliRunner()

    def test_providers(self) -> None:
        from quadkit.cli.commands.inspect import app as inspect_app
        result = self.runner.invoke(inspect_app, ["providers"])
        assert result.exit_code == 0

    def test_routes(self) -> None:
        from quadkit.cli.commands.inspect import app as inspect_app
        result = self.runner.invoke(inspect_app, ["routes"])
        assert result.exit_code == 0

    def test_middleware(self) -> None:
        from quadkit.cli.commands.inspect import app as inspect_app
        result = self.runner.invoke(inspect_app, ["middleware"])
        assert result.exit_code == 0

    def test_container(self) -> None:
        from quadkit.cli.commands.inspect import app as inspect_app
        result = self.runner.invoke(inspect_app, ["container"])
        assert result.exit_code == 0

    def test_events(self) -> None:
        from quadkit.cli.commands.inspect import app as inspect_app
        result = self.runner.invoke(inspect_app, ["events"])
        assert result.exit_code == 0

    def test_tasks(self) -> None:
        from quadkit.cli.commands.inspect import app as inspect_app
        result = self.runner.invoke(inspect_app, ["tasks"])
        assert result.exit_code == 0

    def test_dependencies(self) -> None:
        from quadkit.cli.commands.inspect import app as inspect_app
        result = self.runner.invoke(inspect_app, ["dependencies"])
        assert result.exit_code == 0

    def test_main_unknown_target(self) -> None:
        from quadkit.cli.commands.inspect import app as inspect_app
        result = self.runner.invoke(inspect_app, ["unknown_target"])
        assert result.exit_code != 0

    def test_config_alias(self) -> None:
        from quadkit.cli.commands.inspect import app as inspect_app
        with patch("quadkit.cli.commands.config.show") as mock_show:
            result = self.runner.invoke(inspect_app, ["config"])
            assert result.exit_code == 0
            mock_show.assert_called_once()
