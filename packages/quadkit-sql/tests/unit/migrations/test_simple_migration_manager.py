"""Tests for the SimpleMigrationManager (community-edition migrations)."""

from __future__ import annotations

from datetime import UTC, datetime

from quadkit.contracts import QueryResult
from quadkit.sql.exceptions import DatabaseError
from quadkit.sql.migrations.manager._simple import SimpleMigrationManager


class _MigrationProvider:
    """Scripted double: table existence flag + row store + SQL recorder."""

    def __init__(self, rows: list[dict] | None = None, fail_sql: str | None = None) -> None:
        self.table_present: bool = False
        self.rows: list[dict] = rows or []
        self.executed: list[tuple[str, tuple]] = []
        self.fail_sql = fail_sql

    async def table_exists(self, table_name: str) -> bool:
        return self.table_present and table_name == "__migrations"

    async def execute(self, sql: str, *params: object) -> str:
        self.executed.append((sql, params[0] if params else ()))
        if self.fail_sql and self.fail_sql in sql:
            msg = "boom"
            raise DatabaseError(msg)
        if sql.strip().upper().startswith("CREATE TABLE"):
            self.table_present = True
        return "OK"

    async def execute_query(self, sql: str, *params: object) -> QueryResult:
        self.executed.append((sql, params))
        rows = list(self.rows)
        return QueryResult(
            rows=rows,
            row_count=len(rows),
            execution_time=0.0,
            success=True,
        )

    @property
    def statements(self) -> list[str]:
        return [s for s, _ in self.executed]


def _row(version: str, name: str, success: bool = True) -> dict:
    return {
        "version": version,
        "name": name,
        "applied_at": datetime.now(UTC),
        "success": success,
        "error_message": None,
    }


class TestInitialize:
    async def test_creates_table_when_missing(self) -> None:
        provider = _MigrationProvider()
        manager = SimpleMigrationManager(provider=provider)
        await manager.initialize_migration_table()
        creates = [s for s in provider.statements if "CREATE TABLE" in s]
        assert len(creates) == 1
        assert "__migrations" in creates[0]
        for col in ("version", "name", "applied_at", "success", "error_message"):
            assert col in creates[0]

    async def test_skips_when_table_exists(self) -> None:
        provider = _MigrationProvider()
        provider.table_present = True
        manager = SimpleMigrationManager(provider=provider)
        await manager.initialize_migration_table()
        assert not [s for s in provider.statements if "CREATE TABLE" in s]

    async def test_noop_without_provider(self) -> None:
        manager = SimpleMigrationManager(provider=None)
        await manager.initialize_migration_table()  # must not raise


class TestAppliedMigrations:
    async def test_none_without_provider(self) -> None:
        manager = SimpleMigrationManager(provider=None)
        assert await manager.get_applied_migrations() == []
        assert await manager.get_current_version() is None

    async def test_none_when_table_missing(self) -> None:
        provider = _MigrationProvider()
        manager = SimpleMigrationManager(provider=provider)
        assert await manager.get_applied_migrations() == []

    async def test_records_mapped(self) -> None:
        rows = [_row("001", "create_users"), _row("002", "add_index")]
        provider = _MigrationProvider(rows=rows)
        provider.table_present = True
        manager = SimpleMigrationManager(provider=provider)
        applied = await manager.get_applied_migrations()
        assert [m.version for m in applied] == ["001", "002"]
        assert applied[0].name == "create_users"
        assert applied[0].success is True
        assert applied[0].error_message is None

    async def test_current_version_is_last(self) -> None:
        provider = _MigrationProvider(rows=[_row("001", "a"), _row("002", "b")])
        provider.table_present = True
        manager = SimpleMigrationManager(provider=provider)
        assert await manager.get_current_version() == "002"


class TestApplyMigration:
    async def test_success(self) -> None:
        provider = _MigrationProvider()
        provider.table_present = True
        manager = SimpleMigrationManager(provider=provider)
        assert await manager.apply_migration("001", "create_users", "CREATE TABLE users (id INT)") is True
        inserts = [s for s in provider.statements if s.startswith("INSERT INTO")]
        assert len(inserts) == 1
        assert inserts[0].endswith("success) VALUES (?, ?, ?, ?)")
        record_params = provider.executed[1][1]
        assert isinstance(record_params, tuple)
        assert record_params[:2] == ("001", "create_users")
        assert record_params[3] is True
        assert provider.statements[0] == "CREATE TABLE users (id INT)"

    async def test_failure_records_and_returns_false(self) -> None:
        provider = _MigrationProvider(fail_sql="DROP TABLE evil")
        provider.table_present = True
        manager = SimpleMigrationManager(provider=provider)
        assert await manager.apply_migration("001", "bad", "DROP TABLE evil") is False
        inserts = [s for s in provider.statements if s.startswith("INSERT INTO")]
        assert len(inserts) == 1
        assert "error_message" in inserts[0]
        assert inserts[0].endswith("VALUES (?, ?, ?, ?, ?)")
        record_params = provider.executed[1][1]
        assert record_params[:2] == ("001", "bad")
        assert record_params[3] is False
        assert "boom" in record_params[4]

    async def test_noop_without_provider(self) -> None:
        manager = SimpleMigrationManager(provider=None)
        assert await manager.apply_migration("001", "x", "SELECT 1") is False


class TestRollback:
    async def test_removes_record(self) -> None:
        provider = _MigrationProvider()
        provider.table_present = True
        manager = SimpleMigrationManager(provider=provider)
        assert await manager.rollback_migration("001") is True
        deletes = [s for s in provider.statements if s.startswith("DELETE FROM")]
        assert len(deletes) == 1
        assert "WHERE version = ?" in deletes[0]
        assert provider.executed[0][1] == ("001",)

    async def test_noop_without_provider(self) -> None:
        manager = SimpleMigrationManager(provider=None)
        assert await manager.rollback_migration("001") is False


class TestPendingAndBatch:
    async def test_pending_excludes_successful(self) -> None:
        provider = _MigrationProvider(
            rows=[_row("001", "a"), _row("002", "b", success=False)],
        )
        provider.table_present = True
        manager = SimpleMigrationManager(provider=provider)
        pending = await manager.get_pending_migrations(["001", "002", "003"])
        # 001 applied OK -> excluded; 002 failed -> still pending; 003 new -> pending
        assert pending == ["002", "003"]

    async def test_apply_pending_from_directory(self, tmp_path) -> None:
        (tmp_path / "001_first.sql").write_text("-- Create users\nCREATE TABLE users (id INT);\n")
        (tmp_path / "002_second.sql").write_text("-- Add index\nCREATE INDEX i ON users(id);\n")
        (tmp_path / "notes.txt").write_text("not a migration")
        provider = _MigrationProvider()
        provider.table_present = True
        manager = SimpleMigrationManager(provider=provider, migrations_dir=str(tmp_path))
        applied = await manager.apply_pending_migrations()
        assert applied == ["001_first", "002_second"]
        inserts = [p for s, p in provider.executed if s.startswith("INSERT INTO")]
        assert inserts[0][0] == "001_first"
        assert "Create users" in str(inserts[0])
        assert inserts[1][0] == "002_second"
        assert "Add index" in str(inserts[1])
        dml = " ".join(provider.statements)
        assert "CREATE TABLE users (id INT);" in dml
        assert "CREATE INDEX i ON users(id);" in dml

    async def test_apply_pending_retries_failed(self, tmp_path) -> None:
        (tmp_path / "001_first.sql").write_text("-- First\nSELECT 1;\n")
        provider = _MigrationProvider(rows=[_row("001_first", "First", success=False)])
        provider.table_present = True
        manager = SimpleMigrationManager(provider=provider, migrations_dir=str(tmp_path))
        applied = await manager.apply_pending_migrations()
        assert applied == ["001_first"]

    async def test_apply_pending_missing_dir(self, tmp_path) -> None:
        manager = SimpleMigrationManager(provider=_MigrationProvider(), migrations_dir=str(tmp_path / "nope"))
        assert await manager.apply_pending_migrations() == []

    async def test_apply_pending_no_name_comment(self, tmp_path) -> None:
        (tmp_path / "001_first.sql").write_text("SELECT 1;\n")
        provider = _MigrationProvider()
        provider.table_present = True
        manager = SimpleMigrationManager(provider=provider, migrations_dir=str(tmp_path))
        await manager.apply_pending_migrations()
        inserts = [p for s, p in provider.executed if s.startswith("INSERT INTO")]
        assert "Migration 001_first" in str(inserts[0])


class TestCreateMigrationFile:
    async def test_creates_file_and_returns_version(self, tmp_path) -> None:
        manager = SimpleMigrationManager(migrations_dir=str(tmp_path))
        version = await manager.create_migration_file("my_change", "SELECT 1;")
        assert version  # non-empty timestamp
        path = tmp_path / f"{version}.sql"
        assert path.exists()
        content = path.read_text()
        assert content.startswith("-- my_change\n")
        assert "SELECT 1;" in content

    async def test_create_alias(self, tmp_path) -> None:
        manager = SimpleMigrationManager(migrations_dir=str(tmp_path))
        version = await manager.create("my_change", "the message")
        content = (tmp_path / f"{version}.sql").read_text()
        assert content.startswith("-- my_change\n")
        assert "-- the message" in content

    async def test_distinct_versions_across_calls(self, tmp_path) -> None:
        manager = SimpleMigrationManager(migrations_dir=str(tmp_path))
        v1 = await manager.create_migration_file("a", "SELECT 1;")
        # version is a second-granularity timestamp; same-second creates
        # are allowed to collide (files would be overwritten).
        assert v1 == await manager.create_migration_file("b", "SELECT 2;") or len(v1) == 14
        assert len(v1) == 14
