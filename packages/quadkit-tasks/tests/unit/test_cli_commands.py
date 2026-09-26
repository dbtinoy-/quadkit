"""Tests for the tasks CLI command group factory."""

from __future__ import annotations

import pytest

from quadkit.tasks.cli.commands import create_tasks_app


@pytest.fixture
def app() -> object:
    """Fresh tasks CLI app per test."""
    return create_tasks_app()


def _command_names(typer_app: object) -> list[str]:  # noqa: D103  # noqa: D103
    """Collect registered command/group names from a Typer app."""
    registered = getattr(typer_app, "registered_commands", None)
    if registered:
        return sorted(c.name for c in registered)
    groups = getattr(typer_app, "registered_groups", None)
    return sorted(g.name for g in groups or [])


class TestAppStructure:
    """Structure of the generated tasks CLI app."""

    def test_returns_typer_app(self, app: object) -> None:  # noqa: D102
        import typer

        assert isinstance(app, typer.Typer)

    def test_top_level_commands(self, app: object) -> None:  # noqa: D102
        names = _command_names(app)
        assert "list" in names
        assert "inspect" in names
        assert "retry" in names
        assert "cancel" in names
        assert "purge" in names

    def test_workers_subgroup_registered(self, app: object) -> None:  # noqa: D102
        groups = getattr(app, "registered_groups", [])
        group_names = [g.name for g in groups or []]
        assert "workers" in group_names


class TestWorkersSubgroup:
    """The workers sub-app exposes its own commands."""

    def test_worker_commands(self, app: object) -> None:  # noqa: D102
        groups = list(getattr(app, "registered_groups", []))
        workers_group = next(g for g in groups if g.name == "workers")
        commands = list(getattr(workers_group, "registered_commands", []) or [])
        # fall back to the typer command registry if available
        names = [c.name for c in commands]
        if not names:
            import typer.main

            info = typer.main.get_command(app)
            sub = info.commands  # type: ignore[union-attr]
            workers_cmd = sub["workers"]
            names = list(workers_cmd.commands)  # type: ignore[union-attr]
        assert "list" in names
        assert "status" in names


class TestCommandSignatures:
    """Click parameter shapes of the generated commands."""

    def test_inspect_requires_task_id(self, app: object) -> None:  # noqa: D102
        import typer.main

        info = typer.main.get_command(app)
        cmd = info.commands["inspect"]  # type: ignore[union-attr]
        params = [p.name for p in cmd.params]
        assert "task_id" in params

    def test_purge_defaults(self, app: object) -> None:  # noqa: D102
        import typer.main

        info = typer.main.get_command(app)
        cmd = info.commands["purge"]  # type: ignore[union-attr]
        by_name = {p.name: p for p in cmd.params}
        assert by_name["status"].default == "failed"
        assert by_name["force"].default is False
        assert by_name["queue"].default is None

    def test_list_defaults(self, app: object) -> None:  # noqa: D102
        import typer.main

        info = typer.main.get_command(app)
        cmd = info.commands["list"]  # type: ignore[union-attr]
        by_name = {p.name: p for p in cmd.params}
        assert by_name["limit"].default == 20
        assert by_name["status"].default is None
        assert by_name["queue"].default is None
