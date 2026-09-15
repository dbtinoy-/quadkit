from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from quadkit.cli.commands.shell import _banner


class TestShellBanner:
    def test_banner_returns_string(self) -> None:
        banner = _banner()
        assert isinstance(banner, str)
        assert "Quadkit Interactive Shell" in banner


class TestShellCommand:
    runner = CliRunner()

    @patch("quadkit.cli.commands.shell._run_plain_repl")
    def test_shell_no_app(self, mock_repl: MagicMock) -> None:
        from quadkit.cli.commands.shell import app
        result = self.runner.invoke(app, ["--no-app"])
        assert result.exit_code == 0
        mock_repl.assert_called_once_with(False)

    @patch("quadkit.cli.commands.shell._run_plain_repl")
    def test_shell_no_app_with_ipython(self, mock_repl: MagicMock) -> None:
        from quadkit.cli.commands.shell import app
        result = self.runner.invoke(app, ["--no-app", "--ipython"])
        assert result.exit_code == 0
        mock_repl.assert_called_once_with(True)

    @patch("quadkit.cli.commands.shell._run_repl_with_app")
    def test_shell_with_app(self, mock_repl: MagicMock) -> None:
        from quadkit.cli.commands.shell import app
        result = self.runner.invoke(app, [])
        assert result.exit_code == 0
        mock_repl.assert_called_once_with(False)

    @patch("quadkit.cli.commands.shell._run_repl_with_app")
    def test_shell_with_app_and_ipython(self, mock_repl: MagicMock) -> None:
        from quadkit.cli.commands.shell import app
        result = self.runner.invoke(app, ["--ipython"])
        assert result.exit_code == 0
        mock_repl.assert_called_once_with(True)


class TestRunPlainRepl:
    @patch("code.interact")
    def test_plain_repl_uses_code(self, mock_interact: MagicMock) -> None:
        from quadkit.cli.commands.shell import _run_plain_repl
        _run_plain_repl(use_ipython=False)
        mock_interact.assert_called_once()

    @patch("code.interact")
    def test_plain_repl_ipython_fallback(self, mock_interact: MagicMock) -> None:
        from quadkit.cli.commands.shell import _run_plain_repl
        with patch("importlib.import_module") as mock_import:
            def _side_effect(name, *args, **kwargs):
                if name == "IPython":
                    raise ImportError(f"No module named {name}")
                return __import__(name, *args, **kwargs)
            mock_import.side_effect = _side_effect
            _run_plain_repl(use_ipython=True)
        mock_interact.assert_called_once()


class TestRunReplWithApp:
    @patch("code.interact")
    def test_repl_with_app_uses_code(self, mock_interact: MagicMock) -> None:
        from quadkit.cli.commands.shell import _run_repl_with_app
        _run_repl_with_app(use_ipython=False)
        mock_interact.assert_called_once()

    @patch("code.interact")
    def test_repl_with_app_ipython_fallback(self, mock_interact: MagicMock) -> None:
        from quadkit.cli.commands.shell import _run_repl_with_app
        with patch("importlib.import_module") as mock_import:
            def _side_effect(name, *args, **kwargs):
                if name == "IPython":
                    raise ImportError(f"No module named {name}")
                return __import__(name, *args, **kwargs)
            mock_import.side_effect = _side_effect
            _run_repl_with_app(use_ipython=True)
        mock_interact.assert_called_once()
