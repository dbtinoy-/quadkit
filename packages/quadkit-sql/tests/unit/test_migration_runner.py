"""Tests for MigrationRunnerAdapter."""

from __future__ import annotations

from quadkit.sql.migrations.manager import SimpleMigrationManager
from quadkit.sql.migrations.runner import MigrationRunnerAdapter
from quadkit.sql.migrations.types import MigrationInfo, MigrationStatus


class _FakeAlembicManager:
    """Stands in for AlembicManager: introspector + status introspection."""

    introspector = object()

    def __init__(self, pending: list[str]) -> None:
        self._pending = pending

    async def get_status(self) -> MigrationStatus:
        return MigrationStatus(
            current_revision=None,
            head_revision=None,
            is_up_to_date=not self._pending,
            pending_migrations=[
                MigrationInfo(revision=rev, version=rev, description="")
                for rev in self._pending
            ],
        )


async def test_alembic_manager_pending_comes_from_status() -> None:
    adapter = MigrationRunnerAdapter(_FakeAlembicManager(["b", "c"]))
    assert await adapter.get_pending_migrations() == ["b", "c"]


async def test_file_based_manager_pending_comes_from_disk(tmp_path) -> None:
    (tmp_path / "001_init.sql").write_text("-- init")
    (tmp_path / "002_users.sql").write_text("-- users")
    (tmp_path / "002_users.down.sql").write_text("-- down")
    manager = SimpleMigrationManager(provider=None, migrations_dir=str(tmp_path))
    adapter = MigrationRunnerAdapter(manager)
    assert await adapter.get_pending_migrations() == ["001_init", "002_users"]


__all__ = [
    "test_alembic_manager_pending_comes_from_status",
    "test_file_based_manager_pending_comes_from_disk",
]
