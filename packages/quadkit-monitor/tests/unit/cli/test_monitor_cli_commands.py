"""Tests for the monitor CLI command group factory."""

from __future__ import annotations

import typer
import typer.main

from quadkit.monitor.cli.commands import create_monitor_app


def _info(app: typer.Typer) -> object:
    return typer.main.get_command(app)


def _group_names(app: typer.Typer) -> set[str]:
    return {g.name for g in getattr(app, "registered_groups", []) or []}


def _commands(app: typer.Typer) -> list[str]:
    return sorted(c.name for c in getattr(app, "registered_commands", []) or [])


class TestMonitorApp:
    def test_returns_typer_app(self) -> None:
        app = create_monitor_app()
        assert isinstance(app, typer.Typer)

    def test_top_level_status_command(self) -> None:
        app = create_monitor_app()
        assert "status" in _commands(app)

    def test_subgroups_registered(self) -> None:
        app = create_monitor_app()
        names = _group_names(app)
        assert {"metrics", "slo", "alerts"} <= names

    def test_metrics_list_command(self) -> None:
        app = create_monitor_app()
        info = _info(app)
        sub = info.commands  # type: ignore[union-attr]
        metrics_cmds = list(sub["metrics"].commands)  # type: ignore[union-attr]
        assert "list" in metrics_cmds

    def test_slo_status_command(self) -> None:
        app = create_monitor_app()
        info = _info(app)
        sub = info.commands  # type: ignore[union-attr]
        slo_cmds = list(sub["slo"].commands)  # type: ignore[union-attr]
        assert "status" in slo_cmds

    def test_alerts_list_command(self) -> None:
        app = create_monitor_app()
        info = _info(app)
        sub = info.commands  # type: ignore[union-attr]
        alerts_cmds = list(sub["alerts"].commands)  # type: ignore[union-attr]
        assert "list" in alerts_cmds

    def test_alerts_active_flag_default(self) -> None:
        app = create_monitor_app()
        info = _info(app)
        sub = info.commands  # type: ignore[union-attr]
        cmd = sub["alerts"].commands["list"]  # type: ignore[union-attr]
        by_name = {p.name: p for p in cmd.params}
        assert by_name["active_only"].default is False

    def test_metrics_category_default_none(self) -> None:
        app = create_monitor_app()
        info = _info(app)
        sub = info.commands  # type: ignore[union-attr]
        cmd = sub["metrics"].commands["list"]  # type: ignore[union-attr]
        by_name = {p.name: p for p in cmd.params}
        assert by_name["category"].default is None
