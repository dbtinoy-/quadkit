import pytest

from quadkit.sql.providers.base_provider import DatabaseDriver


class MockProvider(DatabaseDriver):
    async def _create_connection(self):
        return object()

    async def _close_connection(self, connection):
        pass

    async def _execute_query_raw(self, connection, sql, params=None):
        return []

    async def _execute_modify_raw(self, connection, sql, params=None):
        return 0

    async def _begin_transaction_raw(self, connection, isolation=None):
        # begin success
        return

    async def _commit_transaction_raw(self, connection):
        return

    async def _rollback_transaction_raw(self, connection):
        # Simulate rollback failure
        raise RuntimeError("rollback failed")

    async def _get_last_insert_id(self, connection, table):
        return None


@pytest.mark.asyncio
async def test_transaction_rollback_failure_logs(capsys):
    provider = MockProvider("sqlite:///:memory:")

    with pytest.raises(RuntimeError):
        async with provider.transaction():
            raise RuntimeError("operation failed")

    assert "Rollback failed in DatabaseDriver.transaction" in capsys.readouterr().out
