"""Tests for the migration_status admin widget handler."""

from __future__ import annotations

from quadkit.contracts.admin import WidgetParams
from quadkit.result import Ok
from quadkit.sql.admin.handlers.migration_status import MigrationStatusWidgetHandler


class _FakeMigrations:
    def __init__(self, applied: list) -> None:
        self._applied = applied

    async def get_applied_migrations(self) -> list:
        return self._applied


class _FakeRunner:
    def __init__(self, pending: list) -> None:
        self._pending = pending

    async def get_pending_migrations(self) -> list:
        return self._pending


async def test_migration_status_reports_real_counts() -> None:
    handler = MigrationStatusWidgetHandler(
        _FakeMigrations(["a", "b"]), _FakeRunner(["c"])
    )
    result = await handler.get_data(WidgetParams(time_window_minutes=60))
    assert isinstance(result, Ok)
    values = [s.value for s in result.unwrap().stats]
    assert "2 applied" in values
    assert "1 pending" in values


async def test_migration_status_no_pending_is_success() -> None:
    handler = MigrationStatusWidgetHandler(
        _FakeMigrations(["a", "b"]), _FakeRunner([])
    )
    result = await handler.get_data(WidgetParams(time_window_minutes=60))
    assert isinstance(result, Ok)
    values = [s.value for s in result.unwrap().stats]
    assert "2 applied" in values
    assert "0 pending" in values


async def test_migration_status_degrades_when_manager_missing() -> None:
    handler = MigrationStatusWidgetHandler(None)
    result = await handler.get_data(WidgetParams(time_window_minutes=60))
    assert isinstance(result, Ok)
    values = [s.value for s in result.unwrap().stats]
    assert "Unavailable" in values
    assert "Unavailable" in values


__all__ = [
    "test_migration_status_no_pending_is_success",
    "test_migration_status_reports_real_counts",
]
