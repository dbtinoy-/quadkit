import pytest

from quadkit.sql.providers.base_provider import DatabaseDriver


class DummyProvider(DatabaseDriver):
    async def _create_connection(self):
        pass

    async def _close_connection(self, connection):
        pass

    async def _execute_query_raw(self, connection, sql, params=None):
        raise RuntimeError("raw failure")

    async def _execute_modify_raw(self, connection, sql, params=None):
        return 0

    async def _begin_transaction_raw(self, connection, isolation=None):
        pass

    async def _commit_transaction_raw(self, connection):
        pass

    async def _rollback_transaction_raw(self, connection):
        pass

    async def _get_last_insert_id(self, connection, table):
        return None


@pytest.mark.asyncio
async def test_table_exists_fallback_probe(monkeypatch, capsys):
    provider = DummyProvider("sqlite:///:memory:")

    # First call to execute_query should raise, second call should return a result
    calls = {"count": 0}

    async def fake_execute_query(sql, params=None, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("boom")

        class R:
            rows = [{"dummy": 1}]

        return R()

    monkeypatch.setattr(provider, "execute_query", fake_execute_query)

    res = await provider.table_exists("some_table")
    assert res is True
    assert "table_exists primary check failed" in capsys.readouterr().out
