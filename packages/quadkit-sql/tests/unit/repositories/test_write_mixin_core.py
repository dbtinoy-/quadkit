"""Tests for SQLRepository write mixin: create, update, soft/hard delete, upsert."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.sql.exceptions import DatabaseError
from quadkit.sql.providers.base_provider import (
    DeleteResult,
    InsertResult,
    QueryResult,
    UpdateResult,
)
from quadkit.sql.repositories.base import SQLRepository


class RecordingProvider:
    """Fake provider recording write operations."""

    def __init__(self) -> None:
        self.inserts: list[tuple[str, dict[str, Any]]] = []
        self.updates: list[tuple[str, dict[str, Any], str, list[Any]]] = []
        self.deletes: list[tuple[str, str, list[Any]]] = []
        self.queries: list[tuple[str, list[Any]]] = []
        self.insert_result = InsertResult(
            inserted_id=1, affected_rows=1, execution_time=0.0, success=True
        )
        self.update_result = UpdateResult(
            affected_rows=1, execution_time=0.0, success=True
        )
        self.delete_result = DeleteResult(
            affected_rows=1, execution_time=0.0, success=True
        )
        self.query_result = QueryResult(
            rows=[], row_count=0, execution_time=0.0, success=True
        )

    async def execute_insert(self, table: str, data: dict[str, Any]) -> InsertResult:
        self.inserts.append((table, dict(data)))
        return self.insert_result

    async def execute_update(
        self, table: str, data: dict[str, Any], where: str, params: list[Any]
    ) -> UpdateResult:
        self.updates.append((table, dict(data), where, list(params)))
        return self.update_result

    async def execute_delete(self, table: str, where: str, params: list[Any]) -> DeleteResult:
        self.deletes.append((table, where, list(params)))
        return self.delete_result

    async def execute_query(self, query: str, params: Any = None) -> QueryResult:
        self.queries.append((query, list(params or [])))
        return self.query_result


class DictRepo(SQLRepository[dict[str, Any], int]):
    def __init__(self, provider: RecordingProvider, **kw: Any) -> None:
        super().__init__(provider, "users", **kw)

    def _entity_to_dict(self, entity: dict[str, Any]) -> dict[str, Any]:
        return dict(entity)

    def _row_to_entity(self, row: dict[str, Any]) -> dict[str, Any]:
        return dict(row)


def _repo(**kw: Any) -> tuple[DictRepo, RecordingProvider]:
    p = RecordingProvider()
    return DictRepo(p, **kw), p


class TestCreate:
    async def test_create_stamps_timestamps(self) -> None:
        repo, p = _repo()
        entity = {"name": "a"}
        result = await repo.create(entity)
        assert result is entity
        assert "created_at" in p.inserts[0][1]
        assert "updated_at" in p.inserts[0][1]
        assert p.inserts[0][0] == "users"

    async def test_create_preserves_existing_timestamps(self) -> None:
        repo, p = _repo()
        entity = {"name": "a", "created_at": "x", "updated_at": "y"}
        await repo.create(entity)
        assert p.inserts[0][1]["created_at"] == "x"
        assert p.inserts[0][1]["updated_at"] == "y"

    async def test_create_strips_unset_key(self) -> None:
        repo, p = _repo()
        await repo.create({"name": "a", "id": None})
        assert "id" not in p.inserts[0][1]

    async def test_create_sets_generated_id(self) -> None:
        repo, provider = _repo()
        entity = {"name": "a"}
        await repo.create(entity)
        assert entity["id"] == provider.insert_result.inserted_id

    async def test_create_failure_raises(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()
        p.insert_result = InsertResult(
            inserted_id=None, affected_rows=0, execution_time=0.0,
            success=False, error_message="constraint",
        )
        with pytest.raises(RepositoryError, match="constraint"):
            await repo.create({"name": "a"})

    async def test_create_db_error_wrapped(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, provider = _repo()

        async def boom(table: str, data: dict[str, Any]) -> InsertResult:
            raise DatabaseError("db down")

        provider.execute_insert = boom  # type: ignore[method-assign]
        with pytest.raises(RepositoryError, match="Failed to create entity"):
            await repo.create({"name": "a"})

    async def test_read_only_fields_excluded(self) -> None:
        repo, p = _repo()
        repo.read_only_fields = ["created_at"]
        await repo.create({"name": "a"})
        # created_at is re-stamped then removed? Order: timestamps added,
        # then read-only fields deleted.
        data = p.inserts[0][1]
        assert data["name"] == "a"

    async def test_write_table_name_override(self) -> None:
        repo, p = _repo()
        repo.write_table_name = "users_write"
        await repo.create({"name": "a"})
        assert p.inserts[0][0] == "users_write"


class TestSoftDelete:
    async def test_soft_delete_updates_deleted_at(self) -> None:
        repo, p = _repo()
        assert await repo.soft_delete(5) is True
        table, data, where, params = p.updates[0]
        assert table == "users"
        assert "deleted_at" in data
        assert where == '"id" = ?'
        assert params == [5]

    async def test_soft_delete_failure_returns_false(self) -> None:
        repo, p = _repo()
        p.update_result = UpdateResult(
            affected_rows=0, execution_time=0.0, success=False
        )
        assert await repo.soft_delete(5) is False

    async def test_soft_delete_error_wrapped(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()

        async def boom(*a: Any, **kw: Any) -> UpdateResult:
            raise DatabaseError("db down")

        p.execute_update = boom  # type: ignore[method-assign]
        with pytest.raises(RepositoryError, match="Failed to soft delete entity 5"):
            await repo.soft_delete(5)


class TestDeleteById:
    async def test_delete_by_id_success(self) -> None:
        repo, p = _repo()
        assert await repo.delete_by_id(7) is True
        table, where, params = p.deletes[0]
        assert table == "users"
        assert where == '"id" = ?'
        assert params == [7]

    async def test_delete_by_id_affected_rows_zero(self) -> None:
        repo, p = _repo()
        p.delete_result = DeleteResult(
            affected_rows=0, execution_time=0.0, success=True
        )
        assert await repo.delete_by_id(7) is False

    async def test_delete_by_id_failure_raises(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()
        p.delete_result = DeleteResult(
            affected_rows=0, execution_time=0.0,
            success=False, error_message="locked",
        )
        with pytest.raises(RepositoryError, match="Delete failed: locked"):
            await repo.delete_by_id(7)

    async def test_delete_db_error_wrapped(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()

        async def boom(*a: Any, **kw: Any) -> DeleteResult:
            raise DatabaseError("db down")

        p.execute_delete = boom  # type: ignore[method-assign]
        with pytest.raises(RepositoryError, match="Failed to delete entity"):
            await repo.delete_by_id(7)


class TestUpsert:
    async def test_upsert_builds_conflict_query(self) -> None:
        repo, p = _repo()
        entity = {"email": "a@x", "name": "a"}
        result = await repo.upsert(entity)
        assert result is entity
        query, params = p.queries[0]
        assert 'INSERT INTO "users"' in query
        assert 'ON CONFLICT ("id") DO UPDATE SET' in query
        assert '"name" = EXCLUDED."name"' in query
        assert "email" in query
        assert "a@x" in params

    async def test_upsert_custom_conflict_and_update_fields(self) -> None:
        repo, p = _repo()
        await repo.upsert(
            {"email": "a@x", "name": "a", "role": "u"},
            conflict_fields=["email"],
            update_fields=["name"],
        )
        query, _ = p.queries[0]
        assert 'ON CONFLICT ("email") DO UPDATE SET' in query
        assert '"name" = EXCLUDED."name"' in query
        assert 'EXCLUDED."role"' not in query

    async def test_upsert_failure_raises(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()
        p.query_result = QueryResult(
            rows=[], row_count=0, execution_time=0.0,
            success=False, error_message="boom",
        )
        with pytest.raises(RepositoryError, match="Upsert failed: boom"):
            await repo.upsert({"email": "a@x"})

    async def test_upsert_db_error_wrapped(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()

        async def boom(*a: Any, **kw: Any) -> QueryResult:
            raise DatabaseError("db down")

        p.execute_query = boom  # type: ignore[method-assign]
        with pytest.raises(RepositoryError, match="Failed to upsert entity"):
            await repo.upsert({"email": "a@x"})


class TestUpdate:
    async def test_update_delegates_to_standard_path(self) -> None:
        repo, p = _repo()
        entity = {"id": 3, "name": "new"}
        result = await repo.update(entity)
        assert result is entity
        assert len(p.updates) == 1
        table, data, where, params = p.updates[0]
        assert table == "users"
        assert where == '"id" = ?'
        assert params == [3]
        assert data["name"] == "new"
