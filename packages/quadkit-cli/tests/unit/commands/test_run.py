from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from quadkit.cli.commands.run import _is_factory, app


class TestIsFactory:
    def test_create_app_is_factory(self) -> None:
        assert _is_factory("create_app") is True

    def test_app_is_not_factory(self) -> None:
        assert _is_factory("app") is False

    def test_asgi_app_is_not_factory(self) -> None:
        assert _is_factory("asgi_app") is False


class TestRunCommand:
    runner = CliRunner()

    @patch("pathlib.Path.exists", return_value=True)
    @patch("quadkit.cli.commands.run.discover_entry_point", return_value="/tmp/fake_app.py")
    @patch("quadkit.cli.commands.run.detect_factory_attr", return_value="create_app")
    @patch("quadkit.cli.commands.run.path_to_module", return_value="fake_app")
    @patch("quadkit.cli.commands.run._server_registry")
    @patch("quadkit.cli.commands.run.ServerManager")
    def test_run_with_auto_detect(
        self,
        mock_manager: MagicMock,
        mock_registry: MagicMock,
        mock_path_mod: MagicMock,
        mock_detect: MagicMock,
        mock_discover: MagicMock,
        mock_exists: MagicMock,
    ) -> None:
        mock_backend = MagicMock()
        mock_backend.name = "uvicorn"
        mock_backend.is_available.return_value = True
        mock_registry.return_value.get.return_value = mock_backend
        mock_registry.return_value.get_default.return_value = mock_backend

        result = self.runner.invoke(app, [])
        assert result.exit_code == 0

    @patch("quadkit.cli.commands.run.Path.exists", return_value=False)
    def test_run_no_entry_point(self, mock_exists: MagicMock) -> None:
        result = self.runner.invoke(app, [])
        assert result.exit_code == 1
        assert "Could not find" in result.stdout

    def test_run_invalid_server(self) -> None:
        with (
            patch("quadkit.cli.commands.run._server_registry") as mock_registry,
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_registry.return_value.get.return_value = None
            mock_registry.return_value.get_available.return_value = []

            result = self.runner.invoke(app, ["my_app", "--server", "invalid"])
            assert result.exit_code != 0

    def test_run_with_target_and_profile(self) -> None:
        with patch("quadkit.cli.commands.run._server_registry") as mock_factory:
            mock_registry = MagicMock()
            mock_factory.return_value = mock_registry
            mock_get = mock_registry.get
            mock_get_default = mock_registry.get_default
            mock_backend = MagicMock()
            mock_backend.name = "uvicorn"
            mock_backend.is_available.return_value = True
            mock_backend.__bool__.return_value = True
            mock_get.return_value = mock_backend
            mock_get_default.return_value = mock_backend

            result = self.runner.invoke(
                app,
                ["--port", "9000", "--profile", "prod", "--no-reload"],
            )
            assert result.exit_code != 0

    def test_run_explicit_target(self) -> None:
        with patch("quadkit.cli.commands.run._server_registry") as mock_factory:
            mock_registry = MagicMock()
            mock_factory.return_value = mock_registry
            mock_get = mock_registry.get
            mock_backend = MagicMock()
            mock_backend.name = "uvicorn"
            mock_backend.is_available.return_value = True
            mock_backend.__bool__.return_value = True
            mock_get.return_value = mock_backend

            result = self.runner.invoke(app, ["--port", "9000"])
            assert result.exit_code != 0

    @patch("quadkit.cli.commands.run.discover_entry_point", return_value="/tmp/test_app.py")
    @patch("quadkit.cli.commands.run.detect_factory_attr", return_value=None)
    @patch("quadkit.cli.commands.run.Path.exists", return_value=True)
    def test_run_no_factory_found(
        self,
        mock_exists: MagicMock,
        mock_detect: MagicMock,
        mock_discover: MagicMock,
    ) -> None:
        result = self.runner.invoke(app, [])
        assert result.exit_code == 1
        assert "No ASGI app or factory" in result.stdout
