import pytest
from unittest.mock import patch

from quadkit.contracts.exceptions import DatabaseError
from quadkit.sql.migrations.manager import ALEMBIC_AVAILABLE, AlembicManager

pytestmark = pytest.mark.skipif(
    not ALEMBIC_AVAILABLE, reason="Alembic not installed"
)


class DummySession:
    def __init__(self):
        self._executed = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, sql, params=None):
        # Simulate statements executing; raise when applying migration
        if sql.strip().upper().startswith("CREATE"):
            raise RuntimeError("apply-failed")
        return None

    async def fetchall(self):
        return []

    async def commit(self):
        pass

    async def rollback(self):
        pass


class DummyProvider:
    def __init__(self):
        self.url = "sqlite:///:memory:"

    def session(self):
        return DummySession()


@pytest.mark.asyncio
async def test_apply_migration_logs_and_raises(tmp_path):
    # Create manager with a dummy provider and migrations path in tmp
    mgr = AlembicManager(DummyProvider(), migrations_path=tmp_path)

    with patch("quadkit.sql.migrations.manager._alembic.logger") as mock_logger:
        with pytest.raises(DatabaseError):
            await mgr.apply_migration("v1", "name", "CREATE TABLE foo (id INT);")

        # Check both error and exception as they are often used interchangeably in mocks
        error_logs = mock_logger.error.call_args_list + mock_logger.exception.call_args_list
        assert any("apply_migration failed" in str(meta) for meta in error_logs)
