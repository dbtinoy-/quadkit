from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quadkit.cli.registry.migration import (
    Migration,
    MigrationBackend,
    MigrationManager,
    MigrationPlan,
    MigrationRegistry,
    SQLMigrationBackend,
    create_migration_manager,
)


class TestMigration:
    def test_creation(self) -> None:
        m = Migration(version="001", name="init", filename="001_init.sql")
        assert m.version == "001"
        assert m.name == "init"
        assert m.filename == "001_init.sql"
        assert m.success is True

    def test_with_applied_at(self) -> None:
        dt = datetime(2024, 1, 1)
        m = Migration(version="001", name="init", filename="001_init.sql", applied_at=dt)
        assert m.applied_at == dt


class TestMigrationPlan:
    def test_empty_plan(self) -> None:
        plan = MigrationPlan()
        assert plan.to_apply == []
        assert plan.to_rollback == []

    def test_with_migrations(self) -> None:
        m = Migration(version="001", name="init", filename="001_init.sql")
        plan = MigrationPlan(to_apply=[m])
        assert len(plan.to_apply) == 1


class TestMigraitonBackend:
    def test_abc_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            MigrationBackend()  # type: ignore[abstract]


class TestSQLMigrationBackend:
    def test_init_creates_directory(self, tmp_path: Path) -> None:
        migrations_dir = tmp_path / "migrations"
        backend = SQLMigrationBackend(provider=MagicMock(), migrations_dir=str(migrations_dir))
        assert migrations_dir.exists()

    @pytest.mark.asyncio
    async def test_get_applied_migrations_empty(self) -> None:
        mock_provider = AsyncMock()
        mock_provider.execute_query.return_value = type("Res", (), {"rows": []})()
        backend = SQLMigrationBackend(provider=mock_provider)
        result = await backend.get_applied_migrations()
        assert result == []

    @pytest.mark.asyncio
    async def test_get_applied_migrations_error(self) -> None:
        mock_provider = AsyncMock()
        mock_provider.execute_query.side_effect = RuntimeError("fail")
        backend = SQLMigrationBackend(provider=mock_provider)
        result = await backend.get_applied_migrations()
        assert result == []

    @pytest.mark.asyncio
    async def test_apply_migration_file_not_found(self) -> None:
        mock_provider = AsyncMock()
        backend = SQLMigrationBackend(provider=mock_provider, migrations_dir="/tmp/nonexistent")
        m = Migration(version="001", name="test", filename="001_test.sql")
        result = await backend.apply_migration(m)
        assert result is False

    @pytest.mark.asyncio
    async def test_apply_migration_error(self, tmp_path: Path) -> None:
        mock_provider = AsyncMock()
        mock_provider.execute.side_effect = RuntimeError("fail")
        backend = SQLMigrationBackend(provider=mock_provider, migrations_dir=str(tmp_path))
        migration_file = tmp_path / "001_test.sql"
        migration_file.write_text("SQL CONTENT")
        m = Migration(version="001", name="test", filename="001_test.sql")
        result = await backend.apply_migration(m)
        assert result is False

    @pytest.mark.asyncio
    async def test_rollback_migration_missing_file(self) -> None:
        mock_provider = AsyncMock()
        backend = SQLMigrationBackend(provider=mock_provider, migrations_dir="/tmp/nonexistent")
        m = Migration(version="001", name="test", filename="001_test.sql")
        result = await backend.rollback_migration(m)
        assert result is False

    @pytest.mark.asyncio
    async def test_create_migration_creates_files(self, tmp_path: Path) -> None:
        mock_provider = MagicMock()
        backend = SQLMigrationBackend(provider=mock_provider, migrations_dir=str(tmp_path))
        version = await backend.create_migration("add_users")
        assert version is not None
        files = list(tmp_path.glob("*"))
        assert len(files) == 2
        assert any("add_users" in f.name for f in files)
        assert any("down.sql" in f.name for f in files)


class TestMigrationRegistry:
    def test_register_and_get(self) -> None:
        registry = MigrationRegistry()
        backend = MagicMock(spec=SQLMigrationBackend)
        registry.register("test", backend)
        assert registry.get("test") is backend

    def test_get_nonexistent(self) -> None:
        registry = MigrationRegistry()
        assert registry.get("nonexistent") is None

    def test_get_all(self) -> None:
        registry = MigrationRegistry()
        backend = MagicMock(spec=SQLMigrationBackend)
        registry.register("a", backend)
        all_backends = registry.get_all()
        assert "a" in all_backends

    def test_empty_registry_by_default(self) -> None:
        registry = MigrationRegistry()
        assert registry.get_all() == {}

class TestMigrationManager:
    @pytest.mark.asyncio
    async def test_get_status_no_dir(self) -> None:
        backend = MagicMock(spec=SQLMigrationBackend)
        backend.get_applied_migrations = AsyncMock(return_value=[])
        manager = MigrationManager(backend)
        status = await manager.get_status()
        assert status["total_applied"] == 0
        assert status["total_pending"] == 0

    @pytest.mark.asyncio
    async def test_migrate_up_no_dir(self) -> None:
        backend = MagicMock(spec=SQLMigrationBackend)
        backend.get_applied_migrations = AsyncMock(return_value=[])
        del backend.migrations_dir
        manager = MigrationManager(backend)
        plan = await manager.migrate_up()
        assert plan.to_apply == []

    @pytest.mark.asyncio
    async def test_migrate_down_no_applied(self) -> None:
        backend = MagicMock(spec=SQLMigrationBackend)
        backend.get_applied_migrations = AsyncMock(return_value=[])
        manager = MigrationManager(backend)
        plan = await manager.migrate_down()
        assert plan.to_rollback == []

    @pytest.mark.asyncio
    async def test_create_migration_delegates(self) -> None:
        backend = MagicMock(spec=SQLMigrationBackend)
        backend.create_migration = AsyncMock(return_value="001_test")
        manager = MigrationManager(backend)
        version = await manager.create_migration("test")
        assert version == "001_test"

    @pytest.mark.asyncio
    async def test_reset(self) -> None:
        backend = MagicMock(spec=SQLMigrationBackend)
        manager = MigrationManager(backend)
        result = await manager.reset()
        assert result is False


class TestCreateMigrationManager:
    def test_create_sql_backend(self) -> None:
        mock_provider = MagicMock()
        with patch("quadkit.cli.registry.migration.Path.mkdir"):
            manager = create_migration_manager(mock_provider)
            assert isinstance(manager, MigrationManager)

    def test_create_unknown_backend(self) -> None:
        with pytest.raises(ValueError):
            create_migration_manager(MagicMock(), backend_name="unknown")
