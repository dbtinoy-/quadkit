"""Unit tests for DatabaseContentCheckpointStore."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from quadkit.contracts.data.sql.database import (
    DatabaseProviderProtocol,
    QueryResult,
)
from quadkit.contracts.workflow.content_checkpoint import (
    ContentCheckpointEntry,
    ContentCheckpointKey,
)
from quadkit.workflow.checkpoint.store_database import (
    DatabaseContentCheckpointStore,
)


class _NoopTransaction:
    """Minimal async context manager used for provider.transaction()."""

    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


def _query_result(rows: list[dict[str, object]]) -> QueryResult:
    return QueryResult(
        rows=rows,
        row_count=len(rows),
        execution_time=0.0,
        success=True,
    )


@pytest.fixture()
def provider() -> MagicMock:
    p = MagicMock(spec=DatabaseProviderProtocol)
    p.transaction = MagicMock(return_value=_NoopTransaction())
    p.execute = AsyncMock(return_value=_query_result([]))
    p.execute_query = AsyncMock(return_value=_query_result([]))
    p.execute_insert = AsyncMock()
    p.execute_delete = AsyncMock()
    return p


@pytest.fixture()
def store(provider: MagicMock) -> DatabaseContentCheckpointStore:
    return DatabaseContentCheckpointStore(provider)


@pytest.fixture()
def sample_key() -> ContentCheckpointKey:
    return ContentCheckpointKey(
        stage_id="test",
        tenant_id="t1",
        input_hash=b"\x00" * 32,
        config_hash=b"\x01" * 32,
    )


@pytest.fixture()
def sample_entry() -> ContentCheckpointEntry:
    return ContentCheckpointEntry(
        output={"result": "ok"},
        output_blob_ref=None,
        completed_at=datetime(2026, 6, 3),
        stage_handler_version="v1",
        output_size_bytes=16,
    )


class TestDatabaseContentCheckpointStore:
    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(
        self, store: DatabaseContentCheckpointStore, sample_key: ContentCheckpointKey
    ):
        result = await store.get(sample_key)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_returns_entry(
        self,
        store: DatabaseContentCheckpointStore,
        provider: MagicMock,
        sample_key: ContentCheckpointKey,
    ):
        provider.execute_query = AsyncMock(
            return_value=_query_result(
                [
                    {
                        "key_str": sample_key.as_str(),
                        "entry_json": (
                            '{"output":{"result":"ok"},"output_blob_ref":null,'
                            '"completed_at":"2026-06-03T00:00:00",'
                            '"stage_handler_version":"v1","output_size_bytes":16,'
                            '"metadata":{}}'
                        ),
                    }
                ]
            )
        )

        result = await store.get(sample_key)
        assert result is not None
        assert result.output == {"result": "ok"}
        assert result.stage_handler_version == "v1"
        provider.execute_query.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_set_inserts_entry(
        self,
        store: DatabaseContentCheckpointStore,
        provider: MagicMock,
        sample_key: ContentCheckpointKey,
        sample_entry: ContentCheckpointEntry,
    ):
        await store.set(sample_key, sample_entry)

        insert_calls = []
        for call in provider.execute.call_args_list:
            sql = call.args[0]
            if "INSERT INTO" in sql:
                insert_calls.append(call)
        assert len(insert_calls) == 1
        sql = insert_calls[0].args[0]
        assert "workflow_content_checkpoints" in sql
        assert "?" in sql
        assert "ON CONFLICT" in sql
        assert "DO NOTHING" in sql
        params = insert_calls[0].args[1]
        assert len(params) == 6

    @pytest.mark.asyncio
    async def test_set_rejects_sql_injection(
        self,
        store: DatabaseContentCheckpointStore,
        provider: MagicMock,
        sample_key: ContentCheckpointKey,
    ):
        malicious_entry = ContentCheckpointEntry(
            output={"data": "'; DROP TABLE workflow_content_checkpoints; --"},
            output_blob_ref=None,
            completed_at=datetime(2026, 6, 3),
            stage_handler_version="v1'; DELETE FROM users; --",
            output_size_bytes=16,
        )

        await store.set(sample_key, malicious_entry)

        insert_calls = []
        for call in provider.execute.call_args_list:
            sql = call.args[0]
            if "INSERT INTO" in sql:
                insert_calls.append(call)
        assert len(insert_calls) == 1
        sql = insert_calls[0].args[0]
        params = insert_calls[0].args[1]

        assert "DROP TABLE" not in sql
        assert "DELETE FROM" not in sql
        assert "'" not in sql[sql.index("VALUES") :]
        assert any("DROP TABLE" in str(p) for p in params)
        assert any("DELETE FROM" in str(p) for p in params)

    @pytest.mark.asyncio
    async def test_get_rejects_sql_injection(
        self,
        store: DatabaseContentCheckpointStore,
        provider: MagicMock,
    ):
        malicious_key = ContentCheckpointKey(
            stage_id="test",
            tenant_id="t1",
            input_hash=b"\x00" * 32,
            config_hash=b"\x01" * 32,
        )
        provider.execute_query = AsyncMock(
            return_value=_query_result(
                [
                    {
                        "key_str": malicious_key.as_str(),
                        "entry_json": (
                            '{"output":{"result":"ok"},"output_blob_ref":null,'
                            '"completed_at":"2026-06-03T00:00:00",'
                            '"stage_handler_version":"v1","output_size_bytes":16,'
                            '"metadata":{}}'
                        ),
                    }
                ]
            )
        )

        await store.get(malicious_key)
        sql = provider.execute_query.await_args.args[0]
        params = provider.execute_query.await_args.args[1]

        assert "?" in sql
        assert malicious_key.as_str() not in sql
        assert malicious_key.as_str() in params

    @pytest.mark.asyncio
    async def test_evict_deletes_entry(
        self,
        store: DatabaseContentCheckpointStore,
        provider: MagicMock,
        sample_key: ContentCheckpointKey,
    ):
        await store.evict(sample_key)

        provider.execute_delete.assert_awaited_once()
        args = provider.execute_delete.await_args
        assert "key_str" in args.args[1]
        assert sample_key.as_str() in args.args[2]

    @pytest.mark.asyncio
    async def test_evict_nonexistent_does_not_raise(
        self,
        store: DatabaseContentCheckpointStore,
        sample_key: ContentCheckpointKey,
    ):
        await store.evict(sample_key)

    @pytest.mark.asyncio
    async def test_list_by_stage_returns_keys(
        self,
        store: DatabaseContentCheckpointStore,
        provider: MagicMock,
    ):
        provider.execute_query = AsyncMock(
            return_value=_query_result(
                [
                    {"key_str": "stage-a|t1|aa|bb"},
                    {"key_str": "stage-a|t1|cc|dd"},
                ]
            )
        )

        result = await store.list_by_stage("stage-a", tenant_id="t1")
        assert len(result) == 2
        assert result[0].stage_id == "stage-a"
        assert result[0].tenant_id == "t1"

    @pytest.mark.asyncio
    async def test_list_by_stage_binds_patterns_and_limit(
        self,
        store: DatabaseContentCheckpointStore,
        provider: MagicMock,
    ):
        provider.execute_query = AsyncMock(
            return_value=_query_result([{"key_str": "stage-a|t1|aa|bb"}])
        )

        await store.list_by_stage("stage-a", tenant_id="t1", limit=5)

        sql = provider.execute_query.await_args.args[0]
        params = provider.execute_query.await_args.args[1]
        assert sql == (
            "SELECT key_str FROM workflow_content_checkpoints "
            "WHERE key_str LIKE ? AND key_str LIKE ? LIMIT ?"
        )
        assert params == ["stage-a|%", "stage-a|t1|%", 5]

    @pytest.mark.asyncio
    async def test_list_by_stage_without_tenant_binds_single_pattern(
        self,
        store: DatabaseContentCheckpointStore,
        provider: MagicMock,
    ):
        provider.execute_query = AsyncMock(return_value=_query_result([]))

        await store.list_by_stage("stage-a", limit=3)

        sql = provider.execute_query.await_args.args[0]
        params = provider.execute_query.await_args.args[1]
        assert sql == (
            "SELECT key_str FROM workflow_content_checkpoints "
            "WHERE key_str LIKE ? LIMIT ?"
        )
        assert params == ["stage-a|%", 3]

    @pytest.mark.asyncio
    async def test_list_by_stage_rejects_sql_injection(
        self,
        store: DatabaseContentCheckpointStore,
        provider: MagicMock,
    ):
        payload = "'); DROP TABLE workflow_content_checkpoints; --"
        provider.execute_query = AsyncMock(return_value=_query_result([]))

        result = await store.list_by_stage(payload, tenant_id=payload, limit=10)

        assert result == []
        sql = provider.execute_query.await_args.args[0]
        params = provider.execute_query.await_args.args[1]
        assert sql.count("?") == 3
        assert "'" not in sql
        assert "DROP TABLE" not in sql
        assert params == [f"{payload}|%", f"{payload}|{payload}|%", 10]

    @pytest.mark.asyncio
    async def test_invalid_table_name_is_rejected(self):
        with pytest.raises(ValueError, match="table name"):
            DatabaseContentCheckpointStore(
                MagicMock(), table_name="invalid-table-name!"
            )

    @pytest.mark.asyncio
    async def test_creates_schema_on_demand(
        self,
        store: DatabaseContentCheckpointStore,
        provider: MagicMock,
        sample_key: ContentCheckpointKey,
    ):
        await store.get(sample_key)
        provider.execute.assert_awaited_once()
        sql = provider.execute.await_args.args[0]
        assert "CREATE TABLE" in sql
        assert "workflow_content_checkpoints" in sql

    @pytest.mark.asyncio
    async def test_schema_created_once(
        self,
        store: DatabaseContentCheckpointStore,
        provider: MagicMock,
        sample_key: ContentCheckpointKey,
    ):
        await store.get(sample_key)
        await store.get(sample_key)
        provider.execute.assert_awaited_once()


class TestDialectTranslation:
    """Placeholder style follows the provider's dialect (round 13).

    The store is written against SQLite ``?`` style; providers such as
    PostgresProvider use ``$1`` style.  Without translation every real
    Postgres/MySQL call would raise on the placeholder syntax.
    """

    def _provider_with_name(self, name: str) -> MagicMock:
        p = MagicMock(spec=DatabaseProviderProtocol)
        p.name = name
        p.transaction = MagicMock(return_value=_NoopTransaction())
        p.execute = AsyncMock(return_value=_query_result([]))
        p.execute_query = AsyncMock(return_value=_query_result([]))
        p.execute_delete = AsyncMock()
        return p

    @pytest.mark.asyncio
    async def test_postgres_get_uses_positional_placeholders(self, sample_key: ContentCheckpointKey) -> None:
        p = self._provider_with_name("postgres")
        store = DatabaseContentCheckpointStore(p)
        await store.get(sample_key)
        data_calls = [c for c in p.execute_query.await_args_list]
        assert data_calls, "expected a data SELECT"
        sql = data_calls[0].args[0]
        assert "$1" in sql
        assert "?" not in sql

    @pytest.mark.asyncio
    async def test_postgres_set_translates_all_placeholders(
        self, sample_key: ContentCheckpointKey, sample_entry: ContentCheckpointEntry
    ) -> None:
        p = self._provider_with_name("postgres")
        store = DatabaseContentCheckpointStore(p)
        await store.set(sample_key, sample_entry)
        insert_calls = [
            c for c in p.execute.await_args_list if "INSERT INTO" in c.args[0]
        ]
        assert len(insert_calls) == 1
        sql = insert_calls[0].args[0]
        assert "$1" in sql and "$6" in sql
        assert "?" not in sql

    @pytest.mark.asyncio
    async def test_postgres_evict_translates_where(self, sample_key: ContentCheckpointKey) -> None:
        p = self._provider_with_name("postgres")
        store = DatabaseContentCheckpointStore(p)
        await store.evict(sample_key)
        sql = p.execute_delete.await_args.args[1]
        assert "$1" in sql
        assert "?" not in sql

    @pytest.mark.asyncio
    async def test_mysql_uses_percent_placeholders(
        self, sample_key: ContentCheckpointKey, sample_entry: ContentCheckpointEntry
    ) -> None:
        p = self._provider_with_name("mysql")
        store = DatabaseContentCheckpointStore(p)
        await store.set(sample_key, sample_entry)
        insert_calls = [
            c for c in p.execute.await_args_list if "INSERT INTO" in c.args[0]
        ]
        sql = insert_calls[0].args[0]
        assert "%s" in sql
        assert "?" not in sql

    @pytest.mark.asyncio
    async def test_unknown_dialect_passes_through_sqlite_style(
        self, sample_key: ContentCheckpointKey
    ) -> None:
        p = self._provider_with_name("weird-dialect")
        store = DatabaseContentCheckpointStore(p)
        await store.get(sample_key)
        sql = p.execute_query.await_args.args[0]
        assert "?" in sql
        assert "$" not in sql
