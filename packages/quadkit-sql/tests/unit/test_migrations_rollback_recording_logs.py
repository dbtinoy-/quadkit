import pytest
from unittest.mock import patch

from quadkit.contracts.exceptions import DatabaseError
from quadkit.sql.migrations.manager import ALEMBIC_AVAILABLE, AlembicManager

pytestmark = pytest.mark.skipif(
    not ALEMBIC_AVAILABLE, reason="Alembic not installed"
)


class BadSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, sql, params=None):
        # Emulate check query returning None (no existing migration)
        if sql.strip().upper().startswith("SELECT VERSION"):

            class Res:
                def fetchone(self):
                    return None

            return Res()
        # Raise on applying migration statement
        if sql.strip().upper().startswith("CREATE"):
            raise RuntimeError("apply-failed")
        return None

    async def fetchall(self):
        return []

    async def rollback(self):
        raise RuntimeError("rollback-failed")

    async def commit(self):
        pass


class BadProvider:
    def __init__(self):
        self.url = "sqlite:///:memory:"

    def session(self):
        return BadSession()


@pytest.mark.asyncio
async def test_apply_migration_rollback_failure_logs(tmp_path):
    mgr = AlembicManager(BadProvider(), migrations_path=tmp_path)

    with patch("quadkit.sql.migrations.manager._alembic.logger") as mock_logger:
        with pytest.raises(DatabaseError):
            await mgr.apply_migration("v1", "name", "CREATE TABLE foo (id INT);")

        assert any(
            "Rollback failed during migration apply" in str(meta)
            for meta in mock_logger.exception.call_args_list
        )
