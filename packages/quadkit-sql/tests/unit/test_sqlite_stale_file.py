"""Tests for stale-database-file detection in the SQLite pool

Covers the deleted-inode case where the database file is unlinked or
replaced while the pool keeps serving the old handle: the pool must
close the stale connection, report UNHEALTHY, and refuse to serve it.
"""

from pathlib import Path

import pytest

from quadkit.contracts.core import HealthStatus
from quadkit.sql.backends.sqlite import SQLiteConnectionPool
from quadkit.sql.exceptions import DatabaseConnectionError

pytest.importorskip("aiosqlite")


@pytest.mark.asyncio
async def test_health_check_unhealthy_when_db_file_deleted(tmp_path: Path) -> None:
    """Deleting the DB file must flip health to UNHEALTHY and close the handle."""
    database = tmp_path / "test.db"
    pool = SQLiteConnectionPool(str(database))
    await pool.initialize()
    assert pool._conn is not None

    database.unlink()

    result = await pool.health_check()
    assert result.status == HealthStatus.UNHEALTHY
    assert "missing" in result.message or "replaced" in result.message
    assert result.details["file_state"] == "missing_or_replaced"
    assert pool._conn is None
    assert pool._is_healthy is False


@pytest.mark.asyncio
async def test_health_check_healthy_when_file_intact(tmp_path: Path) -> None:
    """An intact DB file must remain HEALTHY across health checks."""
    database = tmp_path / "test.db"
    pool = SQLiteConnectionPool(str(database))
    await pool.initialize()

    result = await pool.health_check()
    assert result.status == HealthStatus.HEALTHY
    assert pool._conn is not None


@pytest.mark.asyncio
async def test_get_connection_raises_when_db_file_deleted(tmp_path: Path) -> None:
    """Requests must fail loudly instead of serving the deleted inode."""
    database = tmp_path / "test.db"
    pool = SQLiteConnectionPool(str(database))
    await pool.initialize()

    database.unlink()

    with pytest.raises(DatabaseConnectionError, match="missing or was replaced"):
        async with pool.get_connection():
            pytest.fail("stale connection should never be yielded")


@pytest.mark.asyncio
async def test_get_connection_raises_when_db_file_replaced(tmp_path: Path) -> None:
    """A recreated file (new inode) must also be refused."""
    database = tmp_path / "test.db"
    pool = SQLiteConnectionPool(str(database))
    await pool.initialize()

    database.unlink()
    database.touch()

    assert pool._file_identity is not None
    assert pool._stat_identity() != pool._file_identity

    with pytest.raises(DatabaseConnectionError, match="missing or was replaced"):
        async with pool.get_connection():
            pytest.fail("stale connection should never be yielded")


@pytest.mark.asyncio
async def test_reinitialize_reconnects_to_new_file(tmp_path: Path) -> None:
    """After invalidation, initialize() reconnects to the new file."""
    database = tmp_path / "test.db"
    pool = SQLiteConnectionPool(str(database))
    await pool.initialize()

    database.unlink()
    await pool.health_check()
    assert pool._conn is None

    await pool.initialize()
    assert pool._conn is not None
    assert pool._file_identity == pool._stat_identity()

    result = await pool.health_check()
    assert result.status == HealthStatus.HEALTHY


@pytest.mark.asyncio
async def test_memory_database_skips_file_state_checks() -> None:
    """In-memory databases must never fail the file-state gate."""
    pool = SQLiteConnectionPool(":memory:")
    await pool.initialize()

    assert pool._file_state_ok() is True
    result = await pool.health_check()
    assert result.status == HealthStatus.HEALTHY


def test_never_connected_pool_with_existing_file_is_ok(tmp_path: Path) -> None:
    """A pool that has not connected yet must not false-positive."""
    database = tmp_path / "test.db"
    database.touch()

    pool = SQLiteConnectionPool(str(database))
    assert pool._file_state_ok() is True


def test_never_connected_pool_with_missing_file_is_ok(tmp_path: Path) -> None:
    """A missing file is ok before connecting — SQLite creates it lazily."""
    database = tmp_path / "missing.db"

    pool = SQLiteConnectionPool(str(database))
    assert pool._file_state_ok() is True


@pytest.mark.asyncio
async def test_get_pool_stats_reports_file_state(tmp_path: Path) -> None:
    """Pool stats must reflect the on-disk file state."""
    database = tmp_path / "test.db"
    pool = SQLiteConnectionPool(str(database))
    await pool.initialize()

    stats = await pool.get_pool_stats()
    assert stats["file_state_ok"] is True

    database.unlink()
    stats = await pool.get_pool_stats()
    assert stats["file_state_ok"] is False


def test_stat_identity_returns_none_for_memory() -> None:
    """In-memory databases have no file identity."""
    pool = SQLiteConnectionPool(":memory:")
    assert pool._stat_identity() is None


def test_stat_identity_captures_dev_ino(tmp_path: Path) -> None:
    """File identity captures device and inode numbers."""
    database = tmp_path / "test.db"
    database.touch()

    pool = SQLiteConnectionPool(str(database))
    identity = pool._stat_identity()
    assert identity is not None

    st = Path(database).stat()
    assert identity == (st.st_dev, st.st_ino)
