"""Round 25 hardening pins.

Covers the gap-hunt fixes from the quadkit-sql audit:

- Stale-connection probes must discard on ANY probe failure (driver and
  framework error types included), not just OSError/ConnectionError/
  RuntimeError/AttributeError.
- Backup listing/validation must survive one corrupted backup file.
- Migration discovery must survive one malformed manifest.
- Rollback failures must never mask the original transaction error
  (provider-level and SimpleTransactionManager-level).
- EXPLAIN failures degrade to a warning plan for ANY error type.
- The database health checker must never raise (critical status instead),
  and its no-connect-args fallback must trigger on DBAPI errors too.
- Postgres auto-creation wraps ANY driver failure in ConnectionError.
- table_exists degrades to False on framework errors.
- The outbox store declares its schema (create_table) and the publisher's
  dead-letter path cannot poison the rest of the batch.
"""

from __future__ import annotations

import gzip
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.sql.exceptions import DatabaseError, QueryError


class TestStaleConnectionDiscard:
    """SimpleConnectionPool._validate_connection must discard on any probe failure."""

    def _make_pool(self) -> Any:
        from quadkit.sql.pool.connection import SimpleConnectionPool

        pool = SimpleConnectionPool(
            provider=MagicMock(), min_connections=0, max_connections=10
        )
        pool._initialized = True
        return pool

    @pytest.mark.asyncio
    async def test_is_connected_framework_error_discards(self) -> None:
        pool = self._make_pool()

        class _Conn:
            is_connected = AsyncMock(side_effect=DatabaseError("backend gone"))

        assert await pool._validate_connection(_Conn()) is False

    @pytest.mark.asyncio
    async def test_select1_driver_error_discards(self) -> None:
        pool = self._make_pool()

        # A driver-style exception that is NOT OSError/ConnectionError/
        # RuntimeError/AttributeError must still discard the connection.
        class _DriverError(Exception):
            pass

        class _Conn:
            # No is_connected attribute -> slow path (SELECT 1 ping)
            execute = AsyncMock(side_effect=_DriverError("ConnectionClosedError"))

        assert await pool._validate_connection(_Conn()) is False

    @pytest.mark.asyncio
    async def test_query_error_from_provider_discards(self) -> None:
        pool = self._make_pool()

        class _Conn:
            is_connected = AsyncMock(return_value=True)
            execute = AsyncMock(side_effect=QueryError("server closed connection"))

        assert await pool._validate_connection(_Conn()) is False

    @pytest.mark.asyncio
    async def test_stale_connection_replaced_on_acquire(self) -> None:
        from quadkit.primitives import clock as ambient_clock

        pool = self._make_pool()

        class _Stale:
            execute = AsyncMock(side_effect=DatabaseError("stale"))

        stale = _Stale()
        fresh = object()
        pool._pool.append((stale, ambient_clock.monotonic()))
        pool._create_connection = AsyncMock(return_value=fresh)
        pool._close_connection = AsyncMock()

        conn = await pool._get_connection()

        assert conn is fresh
        pool._close_connection.assert_awaited_once_with(stale)

    @pytest.mark.asyncio
    async def test_healthy_connection_retained(self) -> None:
        pool = self._make_pool()

        class _Conn:
            is_connected = AsyncMock(return_value=True)
            execute = AsyncMock(return_value=None)

        assert await pool._validate_connection(_Conn()) is True


class TestBackupCorruptionIsolation:
    """One corrupted backup file must not abort listing or validation."""

    def _corrupt_gz_path(self, tmp_path: Path) -> Path:
        full = gzip.compress(
            b'{"metadata": {"created_at": "2026-01-01T00:00:00+00:00", '
            b'"tables": ["t"], "record_counts": {"t": 1}}}'
        )
        corrupt = tmp_path / "corrupt.json.gz"
        # Truncated stream: read() raises EOFError (a plain Exception,
        # NOT OSError) — exactly what the old except tuple missed.
        corrupt.write_bytes(full[:12])
        return corrupt

    def _manager(self) -> Any:
        from quadkit.sql.backup.backup_manager import BackupManager

        return BackupManager(connection_pool=MagicMock())

    @pytest.mark.asyncio
    async def test_list_backups_skips_corrupt_file(self, tmp_path: Path) -> None:
        self._corrupt_gz_path(tmp_path)
        valid = tmp_path / "good.json"
        valid.write_text(
            '{"metadata": {"created_at": "2026-01-02T00:00:00+00:00", '
            '"tables": ["t"], "record_counts": {"t": 3}}}'
        )

        result = await self._manager().list_backups(tmp_path)

        assert [b["filename"] for b in result] == ["good.json"]

    @pytest.mark.asyncio
    async def test_validate_backup_corrupt_returns_invalid(self, tmp_path: Path) -> None:
        corrupt = self._corrupt_gz_path(tmp_path)

        result = await self._manager().validate_backup(corrupt)

        assert result["valid"] is False
        assert result["issues"]


class TestMigrationDiscoveryIsolation:
    """One malformed manifest must not abort discovery of the other packages."""

    @pytest.mark.asyncio
    async def test_discover_packages_survives_broken_manifest(
        self, tmp_path: Path
    ) -> None:
        from quadkit.sql.migrations.orchestrator import MigrationOrchestrator

        good_dir = tmp_path / "packages" / "pkg_good" / "migrations"
        bad_dir = tmp_path / "packages" / "pkg_bad" / "migrations"
        good_dir.mkdir(parents=True)
        bad_dir.mkdir(parents=True)
        # A manifest that parses to a YAML list: manifest["path"] -> TypeError
        (bad_dir / "manifest.yaml").write_text("- a\n- b\n")
        (good_dir / "manifest.yaml").write_text("package: pkg_good\n")

        orchestrator = MigrationOrchestrator("sqlite:///:memory:", base_path=tmp_path)

        packages = orchestrator.discover_packages()

        names = [p.get("package") for p in packages]
        assert "pkg_good" in names
        assert "pkg_bad" not in names


class TestRollbackMasking:
    """A rollback failure must not replace the original transaction error."""

    @pytest.mark.asyncio
    async def test_provider_level_rollback_foreign_error(self) -> None:
        from quadkit.sql.providers.base_provider import DatabaseDriver

        class _Provider(DatabaseDriver):
            async def _create_connection(self):
                return object()

            async def _close_connection(self, connection):
                pass

            async def _execute_query_raw(self, connection, sql, params=None):
                return []

            async def _execute_modify_raw(self, connection, sql, params=None):
                return 0

            async def _begin_transaction_raw(self, connection, isolation=None):
                return None

            async def _commit_transaction_raw(self, connection):
                return None

            async def _rollback_transaction_raw(self, connection):
                raise ValueError("rollback exploded")

            async def _get_last_insert_id(self, connection, table):
                return None

        provider = _Provider("sqlite:///:memory:")

        with pytest.raises(DatabaseError, match="commit boom"):
            async with provider.transaction():
                raise DatabaseError("commit boom")

    @pytest.mark.asyncio
    async def test_simple_transaction_manager_rollback_foreign_error(self) -> None:
        from quadkit.sql.unit_of_work.manager import SimpleTransactionManager

        conn = MagicMock()
        conn.execute = AsyncMock(
            side_effect=[None, DatabaseError("commit boom"), ValueError("rollback boom")]
        )
        pool = MagicMock()
        pool.get_connection = _acm(conn)

        manager = SimpleTransactionManager(connection_pool=pool)

        with pytest.raises(DatabaseError, match="commit boom"):
            async with manager.transaction():
                pass


def _acm(conn: Any) -> Any:
    """Build a callable returning an async context manager yielding *conn*."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _acm_inner():
        yield conn

    return lambda: _acm_inner()


class TestExplainDegradation:
    @pytest.mark.asyncio
    async def test_explain_framework_error_returns_warning_plan(self) -> None:
        from quadkit.sql.monitoring.query_analyzer import QueryAnalyzer

        provider = MagicMock()
        provider.execute = AsyncMock(side_effect=DatabaseError("no explain support"))

        plan = await QueryAnalyzer(provider).explain("SELECT 1")

        assert plan.warnings
        assert any("EXPLAIN failed" in w for w in plan.warnings)


class TestHealthCheckerNeverRaises:
    @pytest.mark.asyncio
    async def test_dbapi_error_returns_critical(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from quadkit.sql.monitoring.database_monitor.health import (
            DatabaseHealthChecker,
        )
        from sqlalchemy.exc import OperationalError

        def _boom(*args: Any, **kwargs: Any) -> Any:
            class _Engine:
                def connect(self) -> Any:
                    raise OperationalError("SELECT 1", {}, ConnectionError("refused"))

                def dispose(self) -> None:
                    return None

            return _Engine()

        monkeypatch.setattr("sqlalchemy.create_engine", _boom)

        result = await DatabaseHealthChecker(MagicMock()).check_database_health(
            "sqlite:////nonexistent/x.db", timeout=2.0
        )

        assert result.status == "critical"


class TestPostgresAutoCreate:
    @pytest.mark.asyncio
    async def test_autocreate_driver_error_wrapped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        pytest.importorskip("asyncpg")
        import asyncpg

        from quadkit.sql.providers.postgres_provider import PostgresProvider

        admin_conn = MagicMock()
        admin_conn.execute = AsyncMock(side_effect=asyncpg.InterfaceError("boom"))
        admin_conn.close = AsyncMock()

        async def _fake_connect(**kwargs: Any) -> Any:
            if kwargs.get("database") == "postgres":
                return admin_conn
            raise asyncpg.InvalidCatalogNameError("database does not exist")

        monkeypatch.setattr(asyncpg, "connect", _fake_connect)

        provider = PostgresProvider(
            "postgresql://user:pass@localhost:5432/mydb"
        )

        with pytest.raises(ConnectionError, match="auto-creation failed"):
            await provider._create_connection()


class TestTableExistsDegradation:
    @pytest.mark.asyncio
    async def test_framework_error_returns_false(self) -> None:
        from quadkit.sql.providers.schema_manager import SchemaManager

        crud = MagicMock()
        crud.provider = crud
        crud.execute_query = AsyncMock(side_effect=DatabaseError("db down"))

        assert await SchemaManager(crud_operations=crud).table_exists("users") is False


class TestOutboxHardening:
    @pytest.mark.asyncio
    async def test_create_table_emits_declared_schema(self) -> None:
        from quadkit.sql.outbox.store import SQLOutboxStore

        db = MagicMock()
        db.execute = AsyncMock()
        await SQLOutboxStore(db=db).create_table()

        sql = db.execute.await_args.args[0]
        assert "CREATE TABLE IF NOT EXISTS outbox_events" in sql
        assert "error TEXT" in sql
        assert "status TEXT NOT NULL DEFAULT 'pending'" in sql

    @pytest.mark.asyncio
    async def test_create_table_custom_table_name(self) -> None:
        from quadkit.sql.outbox.store import SQLOutboxStore

        db = MagicMock()
        db.execute = AsyncMock()
        await SQLOutboxStore(db=db, table="my_outbox").create_table()

        sql = db.execute.await_args.args[0]
        assert "CREATE TABLE IF NOT EXISTS my_outbox" in sql

    @pytest.mark.asyncio
    async def test_dead_letter_failure_does_not_poison_batch(self) -> None:
        from quadkit.sql.outbox.publisher import OutboxPublisher

        store = MagicMock()
        store.fetch_pending = AsyncMock(
            return_value=[
                {"id": "1", "payload": "{}", "event_type": "A"},
                {"id": "2", "payload": "{}", "event_type": "B"},
                {"id": "3", "payload": "{}", "event_type": "C"},
            ]
        )
        store.mark_delivered = AsyncMock()
        store.mark_failed = AsyncMock(side_effect=DatabaseError("no error column"))

        bus = MagicMock()
        bus.publish_raw = AsyncMock(
            side_effect=[None, RuntimeError("bus down"), None]
        )

        publisher = OutboxPublisher(store=store, event_bus=bus)
        count = await publisher._process_batch()  # must not raise

        assert count == 3
        assert bus.publish_raw.await_count == 3
        assert store.mark_delivered.await_count == 2
        delivered_ids = {c.args[0] for c in store.mark_delivered.await_args_list}
        assert delivered_ids == {"1", "3"}
