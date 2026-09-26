"""Tests for SQLRepository read mixin: find_by_id, find_many, find_one,
count, exists."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.sql.exceptions import DatabaseError
from quadkit.sql.providers.base_provider import QueryResult
from quadkit.sql.repositories.base import SQLRepository


class QueryRecordingProvider:
    def __init__(self, rows: list[dict[str, Any]] | None = None, success: bool = True) -> None:
        self._rows = rows if rows is not None else []
        self._success = success
        self.queries: list[tuple[str, list[Any] | None]] = []

    def set_rows(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    async def execute_query(self, query: str, params: Any = None) -> QueryResult:
        self.queries.append((query, list(params) if params is not None else None))
        return QueryResult(
            rows=self._rows,
            row_count=len(self._rows),
            execution_time=0.0,
            success=self._success,
            error_message=None if self._success else "boom",
        )


class DictRepo(SQLRepository[dict[str, Any], int]):
    def __init__(self, provider: QueryRecordingProvider, **kw: Any) -> None:
        super().__init__(provider, "users", **kw)

    def _entity_to_dict(self, entity: dict[str, Any]) -> dict[str, Any]:
        return dict(entity)

    def _row_to_entity(self, row: dict[str, Any]) -> dict[str, Any]:
        return dict(row)


def _repo(rows: list[dict[str, Any]] | None = None, **kw: Any) -> tuple[DictRepo, QueryRecordingProvider]:
    p = QueryRecordingProvider(rows)
    return DictRepo(p, **kw), p


class TestFindById:
    async def test_found(self) -> None:
        repo, p = _repo([{"id": 1, "name": "a"}])
        entity = await repo.find_by_id(1)
        assert entity == {"id": 1, "name": "a"}
        query, params = p.queries[0]
        assert 'WHERE "id" = ?' in query
        assert params == [1]

    async def test_not_found_returns_none(self) -> None:
        repo, _ = _repo([])
        assert await repo.find_by_id(99) is None

    async def test_columns_selection(self) -> None:
        repo, p = _repo([{"id": 1}])
        await repo.find_by_id(1, columns=["id", "name"])
        query, _ = p.queries[0]
        assert 'SELECT "id", "name" FROM' in query

    async def test_soft_delete_filter_applied(self) -> None:
        repo, p = _repo([{"id": 1}], soft_delete_enabled=True)
        await repo.find_by_id(1)
        query, _ = p.queries[0]
        assert "AND deleted_at IS NULL" in query

    async def test_soft_delete_filter_disabled_flag(self) -> None:
        repo, p = _repo([{"id": 1}], soft_delete_enabled=True)
        await repo.find_by_id(1, include_deleted=True)
        query, _ = p.queries[0]
        assert "deleted_at" not in query

    async def test_failure_returns_none(self) -> None:
        repo, provider = _repo()
        provider._success = False
        assert await repo.find_by_id(1) is None

    async def test_db_error_wrapped(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()

        async def boom(query: str, params: Any = None) -> QueryResult:
            raise DatabaseError("db down")

        p.execute_query = boom  # type: ignore[method-assign]
        with pytest.raises(RepositoryError, match="Failed to find entity by id 1"):
            await repo.find_by_id(1)


class TestFindMany:
    async def test_returns_all_rows(self) -> None:
        rows = [{"id": 1}, {"id": 2}, {"id": 3}]
        repo, p = _repo(rows)
        result = await repo.find_many()
        assert len(result) == 3
        query, _ = p.queries[0]
        assert 'SELECT * FROM "users"' in query

    async def test_limit_offset_sort(self) -> None:
        repo, p = _repo([])
        await repo.find_many(limit=10, offset=20, sort_by="id", sort_order="desc")
        query, params = p.queries[0]
        assert 'ORDER BY "id" DESC' in query
        assert "LIMIT ?" in query
        assert "OFFSET ?" in query
        assert params == [10, 20]

    async def test_filters_applied(self) -> None:
        repo, p = _repo([])
        await repo.find_many(status="active")
        query, params = p.queries[0]
        assert "status" in query
        assert params == ["active"]

    async def test_empty_result(self) -> None:
        repo, _ = _repo([])
        assert await repo.find_many() == []


class TestFindOne:
    async def test_first_match(self) -> None:
        repo, _ = _repo([{"id": 1}, {"id": 2}])
        result = await repo.find_one(status="x")
        assert result == {"id": 1}

    async def test_none_when_empty(self) -> None:
        repo, _ = _repo([])
        assert await repo.find_one(status="x") is None


class TestCount:
    async def test_count_returns_int(self) -> None:
        repo, p = _repo([{"count": 42}])
        assert await repo.count(status="active") == 42
        query, _ = p.queries[0]
        assert "COUNT(*) as count" in query

    async def test_count_zero_when_no_rows(self) -> None:
        repo, _ = _repo([])
        assert await repo.count() == 0

    async def test_count_failure_wrapped(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()

        async def boom(query: str, params: Any = None) -> QueryResult:
            raise DatabaseError("db down")

        p.execute_query = boom  # type: ignore[method-assign]
        with pytest.raises(RepositoryError, match="Failed to count entities"):
            await repo.count()


class TestExists:
    async def test_exists_true(self) -> None:
        repo, _ = _repo([{"count": 1}])
        assert await repo.exists(email="a@x") is True

    async def test_exists_false_zero_count(self) -> None:
        repo, _ = _repo([{"count": 0}])
        assert await repo.exists(email="nobody@x") is False

    async def test_exists_false_no_rows(self) -> None:
        repo, _ = _repo([])
        assert await repo.exists() is False

    async def test_exists_failure_raises(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, provider = _repo()
        provider._success = False
        with pytest.raises(RepositoryError, match="Failed to check existence"):
            await repo.exists()

    async def test_exists_db_error_wrapped(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, p = _repo()

        async def boom(query: str, params: Any = None) -> QueryResult:
            raise DatabaseError("db down")

        p.execute_query = boom  # type: ignore[method-assign]
        with pytest.raises(RepositoryError, match="Failed to check existence"):
            await repo.exists()
