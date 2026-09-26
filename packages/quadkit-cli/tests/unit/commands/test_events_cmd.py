from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from quadkit.cli.commands.events import _make_evolution


class TestMakeEvolution:
    @patch("importlib.import_module")
    def test_make_evolution_success(self, mock_import: MagicMock) -> None:
        from quadkit.cli.commands.events import _make_evolution
        mock_evo_cls = MagicMock()
        mock_reg_cls = MagicMock()
        mock_store_cls = MagicMock()
        mock_import.side_effect = lambda name: {
            "quadkit.events.schema.evolution": type("evo", (), {"SchemaEvolution": mock_evo_cls}),
            "quadkit.events.schema.registry": type("reg", (), {"SchemaRegistry": mock_reg_cls}),
            "quadkit.events.schema.store": type("store", (), {"InMemorySchemaStore": mock_store_cls}),
        }[name]

        evolution = _make_evolution()
        assert evolution == mock_evo_cls.return_value

    def test_make_evolution_raises_exit(self) -> None:
        import typer
        with patch("importlib.import_module", side_effect=ImportError):
            with pytest.raises(typer.Exit):
                from quadkit.cli.commands.events import _make_evolution
                _make_evolution()


class TestEventsCommand:
    runner = CliRunner()

    @patch("quadkit.cli.commands.events._make_evolution")
    def test_list_event_types(self, mock_evo: MagicMock) -> None:
        from quadkit.cli.commands.events import app as events_app
        result = self.runner.invoke(events_app, ["list"])
        assert result.exit_code == 0
        assert "Registered event types" in result.stdout

    def test_replay(self) -> None:
        from quadkit.cli.commands.events import app as events_app
        result = self.runner.invoke(events_app, ["replay"])
        assert result.exit_code == 0
        assert "not yet implemented" in result.stdout

    @patch("quadkit.cli.commands.events._make_evolution")
    def test_status(self, mock_evo: MagicMock) -> None:
        from quadkit.cli.commands.events import app as events_app
        result = self.runner.invoke(events_app, ["status"])
        assert result.exit_code == 0
        assert "No event schemas registered" in result.stdout


import pytest
