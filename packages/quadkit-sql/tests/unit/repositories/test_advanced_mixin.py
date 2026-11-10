"""Tests for SQLRepository._AdvancedMixin: aggregate, specs, cursor pagination,
streaming, and bulk operations.

Uses a recording fake provider so no real database is required.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from quadkit.sql.exceptions import QueryError
from quadkit.sql.providers.base_provider import QueryResult
from quadkit.sql.repositories.base import SQLRepository
from quadkit.sql.specification import FieldEquals


class FakeProvider:
    """Recording provider double for execute_query."""

    def __init__(self, rows: list[dict[str, Any]] | None = None, success: bool = True) -> None:
        self._rows = rows if rows is not None else []
        self._success = success
        self.queries: list[str] = []
        self.params: list[list[Any]] = []

    async def execute_query(self, query: str, params: Any = None) -> QueryResult:
        self.queries.append(query)
        self.params.append(list(params or []))
        return QueryResult(
            rows=self._rows,
            row_count=len(self._rows),
            execution_time=0.0,
            success=self._success,
            error_message=None if self._success else "boom",
        )


class DictRepo(SQLRepository[dict[str, Any], int]):
    """Minimal concrete repository (entity == row dict)."""

    def __init__(self, provider: FakeProvider, **kw: Any) -> None:
        super().__init__(provider, "users", **kw)

    def _entity_to_dict(self, entity: dict[str, Any]) -> dict[str, Any]:
        return dict(entity)

    def _row_to_entity(self, row: dict[str, Any]) -> dict[str, Any]:
        return dict(row)


def _repo(rows: list[dict[str, Any]] | None = None, **kw: Any) -> tuple[DictRepo, FakeProvider]:
    p = FakeProvider(rows)
    return DictRepo(p, **kw), p


class TestAggregate:
    async def test_count_only_by_default(self) -> None:
        repo, p = _repo([{"count": 42}])
        result = await repo.aggregate()
        assert result == {"count": 42}
        assert "COUNT(*) AS count" in p.queries[0]

    async def test_sum_avg_min_max_single(self) -> None:
        repo, p = _repo([{"price_sum": 100, "price_avg": 5, "price_min": 1, "price_max": 10}])
        result = await repo.aggregate(sum="price", avg="price", min="price", max="price")
        assert result["price_sum"] == 100
        assert 'SUM("price") AS price_sum' in p.queries[0]
        assert 'AVG("price") AS price_avg' in p.queries[0]
        assert 'MIN("price") AS price_min' in p.queries[0]
        assert 'MAX("price") AS price_max' in p.queries[0]

    async def test_list_columns(self) -> None:
        repo, p = _repo([{"a_sum": 1, "b_sum": 2}])
        await repo.aggregate(sum=["a", "b"])
        q = p.queries[0]
        assert 'SUM("a") AS a_sum' in q
        assert 'SUM("b") AS b_sum' in q

    async def test_explicit_count_column(self) -> None:
        repo, p = _repo([{"count": 7}])
        await repo.aggregate(count="email")
        assert 'COUNT("email") AS count' in p.queries[0]

    async def test_group_by_returns_list(self) -> None:
        repo, p = _repo([{"dept": "eng", "count": 3}, {"dept": "sales", "count": 2}])
        result = await repo.aggregate(count="*", group_by="dept")
        assert isinstance(result, list)
        assert len(result) == 2
        assert p.queries[0].endswith('GROUP BY "dept"')
        assert "dept" in p.queries[0].split("FROM")[1]  # group col in SELECT

    async def test_filters_forwarded(self) -> None:
        repo, p = _repo([{"count": 1}])
        await repo.aggregate(count="*", status="active")
        assert p.params[0] == ["active"]
        assert "status" in p.queries[0]

    async def test_typed_filters_reach_the_where_clause(self) -> None:
        """A windowed aggregate takes its bounds as typed filters."""
        from quadkit.sql.repositories.filter_objects import F

        repo, p = _repo([{"count": 3, "quota_sum": 90}])
        result = await repo.aggregate(
            count="id",
            sum="quota",
            filter_expressions=(F("log_time") >= "2026-01-01", F("log_time") <= "2026-01-02"),
        )
        assert result == {"count": 3, "quota_sum": 90}
        query = p.queries[0]
        assert 'WHERE "log_time" >= ? AND "log_time" <= ?' in query
        assert p.params[0] == ["2026-01-01", "2026-01-02"]

    async def test_typed_and_keyword_filters_combine(self) -> None:
        """Keyword equality and typed predicates land in one statement."""
        from quadkit.sql.repositories.filter_objects import F

        repo, p = _repo([{"count": 1}])
        await repo.aggregate(count="id", filter_expressions=(F("status") >= 400,), user_id="u1")
        assert '"status" >= ?' in p.queries[0]
        assert '"user_id" = ?' in p.queries[0]
        assert p.params[0] == [400, "u1"]

    async def test_bucket_is_projected_and_grouped(self) -> None:
        """A bucket is a computed key: selected under its alias and grouped."""
        from quadkit.sql.repositories.filter_objects import Bucket

        repo, p = _repo([{"created_at": 0, "model": "gpt-4o", "count": 2}])
        result = await repo.aggregate(
            count="*",
            group_by="model",
            bucket=Bucket("start_time", 3600, "created_at"),
        )
        query = p.queries[0]
        expression = '("start_time" - ("start_time" % 3600))'
        assert f'SELECT {expression} AS "created_at", "model", COUNT(*) AS count' in query
        assert query.endswith(f'GROUP BY "model", {expression}')
        assert result == [{"created_at": 0, "model": "gpt-4o", "count": 2}]

    async def test_count_distinct_counts_values_not_rows(self) -> None:
        """"How many users" is `COUNT(DISTINCT col)`, not a fetched list.

        A plain `count` answers "how many rows", so a panel asking for the
        number of distinct users with a session had to read every row and count
        in Python. The aggregate projects the distinct count directly.
        """
        repo, p = _repo([{"count_distinct": 3}])
        result = await repo.aggregate(count_distinct="user_id")

        assert 'SELECT COUNT(DISTINCT "user_id") AS count_distinct' in p.queries[0]
        # No bare COUNT(*) is added alongside it.
        assert "COUNT(*) AS count" not in p.queries[0]
        assert result == {"count_distinct": 3}

    async def test_count_and_count_distinct_can_share_a_statement(self) -> None:
        """Both counts can be projected together, and both are aliased."""
        repo, p = _repo([{"count": 10, "count_distinct": 4}])
        result = await repo.aggregate(count="*", count_distinct="user_id")

        query = p.queries[0]
        assert 'COUNT(*) AS count' in query
        assert 'COUNT(DISTINCT "user_id") AS count_distinct' in query
        assert result == {"count": 10, "count_distinct": 4}

    async def test_date_bucket_projects_the_calendar_day(self) -> None:
        """A date bucket groups on ``DATE(column)``, portable across the dialects.

        "Sign-ups per day" is a projection of an expression, so it could not be
        expressed through ``aggregate``'s column-name ``group_by``; callers
        hand-wrote the statement or fetched every row and counted in Python.
        """
        from quadkit.sql.repositories.filter_objects import DateBucket

        repo, p = _repo([{"day": "2026-01-02", "count": 3}])
        result = await repo.aggregate(count="*", bucket=DateBucket("created_at", "day"))

        query = p.queries[0]
        assert 'SELECT DATE("created_at") AS "day", COUNT(*) AS count' in query
        assert query.endswith('GROUP BY DATE("created_at")')
        assert result == [{"day": "2026-01-02", "count": 3}]

    async def test_date_bucket_accepts_several_keys(self) -> None:
        """A date bucket and a numeric bucket share one list and one GROUP BY."""
        from quadkit.sql.repositories.filter_objects import Bucket, DateBucket

        repo, p = _repo([{"day": "2026-01-02", "model": "gpt-4o", "count": 1}])
        await repo.aggregate(
            count="*",
            group_by="model",
            bucket=(DateBucket("created_at", "day"), Bucket("start_time", 3600, "hour")),
        )

        query = p.queries[0]
        assert 'DATE("created_at") AS "day"' in query
        assert '("start_time" - ("start_time" % 3600)) AS "hour"' in query
        assert query.endswith('GROUP BY "model", DATE("created_at"), ("start_time" - ("start_time" % 3600))')

    async def test_date_bucket_rejects_a_bad_column_or_alias(self) -> None:
        """Both halves are validated before any SQL exists."""
        from quadkit.contracts.data.sql.sql import InvalidIdentifierError

        from quadkit.sql.repositories.filter_objects import DateBucket

        with pytest.raises((ValueError, InvalidIdentifierError)):
            DateBucket('created_at"; DROP TABLE t; --', "day")
        with pytest.raises((ValueError, InvalidIdentifierError)):
            DateBucket("created_at", 'day"')

    async def test_bucket_alone_groups_the_statement(self) -> None:
        """`bucket` without `group_by` still returns one row per bucket."""
        from quadkit.sql.repositories.filter_objects import Bucket

        repo, p = _repo([{"created_at": 7200, "count": 5}])
        await repo.aggregate(count="*", bucket=Bucket("start_time", 3600, "created_at"))
        assert p.queries[0].endswith('GROUP BY ("start_time" - ("start_time" % 3600))')

    async def test_bucket_accepts_several_keys(self) -> None:
        """Two buckets project and group together, in declaration order."""
        from quadkit.sql.repositories.filter_objects import Bucket

        repo, p = _repo([{"created_at": 0, "id_sum": 1}])
        await repo.aggregate(
            sum="id",
            bucket=[Bucket("start_time", 3600, "created_at"), Bucket("end_time", 86_400, "day")],
        )
        query = p.queries[0]
        assert '"start_time" - ("start_time" % 3600)) AS "created_at"' in query
        assert '"end_time" - ("end_time" % 86400)) AS "day"' in query
        # Declaration order is preserved in the projection, and each key is
        # both selected and grouped.
        assert query.index("created_at") < query.index('"day"')
        assert "GROUP BY" in query and query.count("% 86400") == 2

    async def test_bucket_rejects_a_bad_size_or_column(self) -> None:
        """Both halves are validated before any SQL is built."""
        from quadkit.contracts.data.sql.sql import InvalidIdentifierError
        from quadkit.sql.repositories.filter_objects import Bucket

        with pytest.raises(ValueError):
            Bucket("start_time", 0, "created_at")
        with pytest.raises(ValueError):
            Bucket("start_time", True, "created_at")  # type: ignore[arg-type]
        with pytest.raises(InvalidIdentifierError):
            Bucket("start_time; DROP TABLE x", 3600, "created_at")
        with pytest.raises(InvalidIdentifierError):
            Bucket("start_time", 3600, "created at")

    async def test_failure_raises_repository_error(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, _ = _repo([])
        repo.provider = FakeProvider(rows=[], success=False)
        with pytest.raises(RepositoryError, match="Aggregate failed"):
            await repo.aggregate()

    async def test_db_error_wrapped(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, _ = _repo()
        p = repo.provider

        async def boom(query: str, params: Any = None) -> QueryResult:
            raise QueryError("db exploded")

        p.execute_query = boom  # type: ignore[method-assign]
        with pytest.raises(RepositoryError, match="Failed to run aggregate"):
            await repo.aggregate()


class TestSpecQueries:
    async def test_find_by_spec(self) -> None:
        repo, p = _repo([{"id": 1, "name": "a"}, {"id": 2, "name": "b"}])
        rows = await repo.find_by_spec(FieldEquals("name", "a"))
        assert len(rows) == 2
        assert 'WHERE "name" = ?' in p.queries[0]
        assert p.params[0] == ["a"]

    async def test_find_by_spec_sort_limit_offset(self) -> None:
        repo, p = _repo([])
        await repo.find_by_spec(FieldEquals("x", 1), limit=10, offset=5, sort_by="id", sort_order="desc")
        q = p.queries[0]
        assert 'ORDER BY "id" DESC' in q
        assert "LIMIT ?" in q
        assert "OFFSET ?" in q
        assert p.params[0] == [1, 10, 5]

    async def test_find_by_spec_failure_returns_empty(self) -> None:
        repo, _ = _repo()
        repo.provider = FakeProvider(rows=[], success=False)
        assert await repo.find_by_spec(FieldEquals("x", 1)) == []

    async def test_count_by_spec(self) -> None:
        repo, p = _repo([{"count": 9}])
        assert await repo.count_by_spec(FieldEquals("x", 1)) == 9
        assert "COUNT(*) AS count" in p.queries[0]

    async def test_count_by_spec_empty(self) -> None:
        repo, _ = _repo([])
        assert await repo.count_by_spec(FieldEquals("x", 1)) == 0

    async def test_count_by_spec_db_error(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, _ = _repo()
        p = repo.provider

        async def boom(query: str, params: Any = None) -> QueryResult:
            raise QueryError("db exploded")

        p.execute_query = boom  # type: ignore[method-assign]
        with pytest.raises(RepositoryError, match="Failed to count by spec"):
            await repo.count_by_spec(FieldEquals("x", 1))


class TestCursorPagination:
    ROWS = [{"id": i, "name": f"n{i}"} for i in range(1, 6)]

    async def test_first_page_with_more(self) -> None:
        repo, p = _repo(self.ROWS)
        page = await repo.paginate_cursor(limit=3, sort_by="id")
        assert len(page.items) == 3
        assert page.has_more is True
        assert page.next_cursor is not None
        assert page.prev_cursor is None
        assert page.has_previous is False
        assert page.total_count is None
        assert 'ORDER BY "id" ASC' in p.queries[0]
        assert p.params[-1] == [4]  # limit+1

    async def test_last_page_no_more(self) -> None:
        repo, _ = _repo(self.ROWS[:2])
        page = await repo.paginate_cursor(limit=3, sort_by="id")
        assert page.has_more is False
        assert page.next_cursor is None

    async def test_desc_order_uses_less_than(self) -> None:
        repo, _ = _repo(self.ROWS)
        from quadkit.sql.repositories.cursor import decode_cursor

        page1 = await repo.paginate_cursor(limit=3, sort_by="id", sort_order="desc")
        assert page1.next_cursor is not None
        data = decode_cursor(page1.next_cursor)
        assert data["id"] == 3  # the 3rd row's id (1-based page of 3 from [5,4,3,2,1])
        _ = data

    async def test_cursor_applied_as_and_condition(self) -> None:
        from quadkit.sql.repositories.cursor import encode_cursor

        repo, p = _repo(self.ROWS[:2])
        cursor = encode_cursor({"id": 3})
        await repo.paginate_cursor(cursor=cursor, limit=3, sort_by="id", status="active")
        q = p.queries[0]
        assert '"id" > ?' in q
        assert " AND " in q  # combined with the filter's WHERE
        params = p.params[0]
        assert 3 in params

    async def test_prev_cursor_set_when_cursor_given(self) -> None:
        from quadkit.sql.repositories.cursor import encode_cursor

        repo, _ = _repo(self.ROWS[:2])
        page = await repo.paginate_cursor(cursor=encode_cursor({"id": 3}), limit=3, sort_by="id")
        assert page.has_previous is True
        assert page.prev_cursor is not None
        from quadkit.sql.repositories.cursor import decode_cursor

        assert decode_cursor(page.prev_cursor)["id"] == 1

    async def test_include_total(self) -> None:
        repo, _ = _repo(self.ROWS[:2])
        repo.count = AsyncMock(return_value=100)  # type: ignore[method-assign]
        page = await repo.paginate_cursor(limit=3, sort_by="id", include_total=True)
        assert page.total_count == 100

    async def test_failure_raises(self) -> None:
        from quadkit.sql.exceptions import RepositoryError

        repo, _ = _repo()
        repo.provider = FakeProvider(rows=[], success=False)
        with pytest.raises(RepositoryError, match="Cursor paginate failed"):
            await repo.paginate_cursor(limit=3, sort_by="id")


class TestOffsetPagination:
    async def test_paginate_structure(self) -> None:
        repo, _ = _repo([{"id": 1}])
        repo.find_many = AsyncMock(return_value=[{"id": 1}])  # type: ignore[method-assign]
        repo.count = AsyncMock(return_value=45)  # type: ignore[method-assign]
        result = await repo.paginate(page=2, per_page=20)
        assert result["data"] == [{"id": 1}]
        assert result["total"] == 45
        assert result["page"] == 2
        assert result["per_page"] == 20
        assert result["total_pages"] == 3  # ceil(45/20)

    async def test_paginate_zero_per_page(self) -> None:
        repo, _ = _repo([])
        repo.find_many = AsyncMock(return_value=[])  # type: ignore[method-assign]
        repo.count = AsyncMock(return_value=0)  # type: ignore[method-assign]
        result = await repo.paginate(page=1, per_page=0)
        assert result["total_pages"] == 0


class TestStream:
    async def test_streams_all_in_batches(self) -> None:
        repo, _ = _repo()
        calls = []

        async def fake_find_many(*args: Any, **kw: Any) -> list[dict[str, Any]]:
            calls.append((kw.get("limit"), kw.get("offset")))
            offset = kw.get("offset", 0)
            rows = [{"id": i} for i in range(offset, offset + 2)]
            return rows[:2] if offset < 4 else []

        repo.find_many = fake_find_many  # type: ignore[method-assign]
        seen: list[Any] = []
        async for entity in repo.stream(batch_size=2):
            seen.append(entity)
        assert [e["id"] for e in seen] == [0, 1, 2, 3]
        assert calls[0] == (2, 0)
        assert calls[-1][1] >= 4


class TestFindOrCreate:
    async def test_finds_existing(self) -> None:
        repo, _ = _repo()
        repo.find_one = AsyncMock(return_value={"id": 1, "email": "a@x"})  # type: ignore[method-assign]
        entity, created = await repo.find_or_create(email="a@x")
        assert created is False
        assert entity["id"] == 1

    async def test_creates_when_missing(self) -> None:
        repo, _ = _repo()
        repo.find_one = AsyncMock(return_value=None)  # type: ignore[method-assign]
        repo.create = AsyncMock(return_value={"id": 9, "email": "n@x", "role": "user"})  # type: ignore[method-assign]
        entity, created = await repo.find_or_create(email="n@x", role="user")
        assert created is True
        assert entity["id"] == 9
        # defaults merged into the created entity
        assert repo.create.call_args.args[0]["role"] == "user"

    async def test_update_or_create_updates_existing(self) -> None:
        repo, _ = _repo()
        repo.find_one = AsyncMock(return_value={"id": 1, "email": "a@x", "role": "old"})  # type: ignore[method-assign]
        repo.update = AsyncMock(return_value={"id": 1, "email": "a@x", "role": "new"})  # type: ignore[method-assign]
        entity, created = await repo.update_or_create(email="a@x", role="new")
        assert created is False
        assert entity["role"] == "new"
        repo.update.assert_awaited_once()

    async def test_update_or_create_creates_missing(self) -> None:
        repo, _ = _repo()
        repo.find_one = AsyncMock(return_value=None)  # type: ignore[method-assign]
        repo.create = AsyncMock(return_value={"id": 5, "k": "v", "extra": 1})  # type: ignore[method-assign]
        entity, created = await repo.update_or_create(k="v", extra=1)
        assert created is True
        assert entity["id"] == 5


class TestBulkOps:
    async def test_bulk_create(self) -> None:
        repo, _ = _repo()
        repo.create = AsyncMock(side_effect=[{"id": 1}, {"id": 2}, {"id": 3}])  # type: ignore[method-assign]
        result = await repo.bulk_create([{"a": 1}, {"a": 2}, {"a": 3}])
        assert [e["id"] for e in result] == [1, 2, 3]
        assert repo.create.await_count == 3

    async def test_bulk_update(self) -> None:
        repo, _ = _repo()
        repo.update = AsyncMock(side_effect=[{"id": 1}, {"id": 2}])  # type: ignore[method-assign]
        result = await repo.bulk_update([{"id": 1}, {"id": 2}])
        assert len(result) == 2

    async def test_bulk_delete_all_success(self) -> None:
        repo, _ = _repo()
        repo.delete = AsyncMock(return_value=True)  # type: ignore[method-assign]
        assert await repo.bulk_delete([1, 2]) is True

    async def test_bulk_delete_partial_failure(self) -> None:
        repo, _ = _repo()
        repo.delete = AsyncMock(side_effect=[True, False, True])  # type: ignore[method-assign]
        assert await repo.bulk_delete([1, 2, 3]) is False
