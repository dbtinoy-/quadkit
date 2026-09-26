"""Tests for the core query builder mixin: DML modes, RETURNING, locks, paging.

Covers the parts of _CoreMixin not exercised by the build-path,
operator, and join/aggregate test files (dialect handling, ON CONFLICT,
row locks, DISTINCT, order/limit/offset, execute_one/execute_scalar).
"""

from __future__ import annotations

from quadkit.sql.query.sql_builder import AsyncQueryBuilder


def _b(table: str = "users") -> AsyncQueryBuilder:
    return AsyncQueryBuilder(table)


class TestInit:
    def test_default_select_mode(self) -> None:
        b = _b()
        assert b.build().sql.startswith("SELECT")

    def test_table_quoted(self) -> None:
        assert '"users"' in _b("users").build().sql

    def test_dialect_attribute(self) -> None:
        from quadkit.contracts.data.sql.sql_dialect import SQLDialect

        assert _b()._dialect is SQLDialect.POSTGRESQL  # noqa: SLF001
        assert AsyncQueryBuilder("t", SQLDialect.MYSQL)._dialect is SQLDialect.MYSQL  # noqa: SLF001

    def test_chaining_returns_self(self) -> None:
        b = _b()
        assert b.select("a").order_by("a").limit(1).offset(0) is b


class TestSelect:
    def test_select_specific_columns(self) -> None:
        sql = _b().select("id", "email").build().sql
        assert '"id"' in sql
        assert '"email"' in sql
        assert "*" not in sql.split("FROM")[0]

    def test_select_star_explicit(self) -> None:
        sql = _b().select("*").build().sql
        assert "SELECT *" in sql


class TestReturning:
    def test_insert_returning(self) -> None:
        sql = _b().insert({"a": 1}).returning("id").build().sql
        assert "RETURNING" in sql
        assert "id" in sql

    def test_update_returning(self) -> None:
        sql = _b().update({"a": 1}).where("id", "=", 1).returning("id", "a").build().sql
        assert "RETURNING" in sql

    def test_returning_triggers_fetch_on_execute(self) -> None:
        b = _b().insert({"a": 1}).returning("id")
        calls: list[str] = []

        class _Conn:
            async def fetch(self, sql: str, *params: object) -> list:
                calls.append("fetch")
                return []

            async def execute(self, sql: str, *params: object) -> str:
                calls.append("execute")
                return "OK"

        result = None
        import asyncio

        async def _main() -> None:
            nonlocal result
            result = await b.execute(_Conn())

        # suite runs under asyncio_mode=auto, but this test is sync; drive it
        # with a fresh loop.
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_main())
        finally:
            loop.close()
        assert calls == ["fetch"]  # returning forces the fetch path


class TestRowLocks:
    def test_for_update(self) -> None:
        sql = _b().for_update().build().sql
        assert "FOR UPDATE" in sql

    def test_for_update_skip_locked(self) -> None:
        sql = _b().for_update(skip_locked=True).build().sql
        assert "FOR UPDATE SKIP LOCKED" in sql

    def test_for_update_no_wait(self) -> None:
        sql = _b().for_update(no_wait=True).build().sql
        assert "FOR UPDATE NOWAIT" in sql

    def test_for_share(self) -> None:
        sql = _b().for_share().build().sql
        assert "FOR SHARE" in sql


class TestPaging:
    def test_limit_offset(self) -> None:
        q = _b().limit(25).offset(50).build()
        assert "LIMIT $1 OFFSET $2" in q.sql
        assert list(q.params) == [25, 50]

    def test_order_by_desc(self) -> None:
        sql = _b().order_by("created_at", desc=True).build().sql
        assert "ORDER BY" in sql
        assert "DESC" in sql

    def test_order_by_asc_default(self) -> None:
        sql = _b().order_by("name").build().sql
        assert "ORDER BY" in sql
        assert "DESC" not in sql


class TestDistinct:
    def test_distinct(self) -> None:
        sql = _b().distinct().build().sql
        assert "SELECT DISTINCT" in sql

    def test_distinct_on(self) -> None:
        sql = _b().distinct("user_id").build().sql
        assert "DISTINCT ON" in sql


class TestOnConflict:
    def test_do_nothing(self) -> None:
        sql = _b().insert({"a": 1}).on_conflict("email").do_nothing().build().sql
        assert "ON CONFLICT" in sql
        assert "DO NOTHING" in sql

    def test_do_update(self) -> None:
        sql = (
            _b()
            .insert({"email": "a@b.c", "n": 1})
            .on_conflict("email")
            .do_update("n")
            .build()
            .sql
        )
        assert "DO UPDATE SET" in sql
        assert "n" in sql


class TestExecuteVariants:
    async def test_execute_one_returns_dict(self) -> None:
        class _Conn:
            async def fetchrow(self, sql: str, *params: object) -> dict | None:
                return {"id": 7}

        row = await _b().execute_one(_Conn())
        assert row == {"id": 7}

    async def test_execute_one_none(self) -> None:
        class _Conn:
            async def fetchrow(self, sql: str, *params: object) -> dict | None:
                return None

        assert await _b().execute_one(_Conn()) is None

    async def test_execute_scalar(self) -> None:
        class _Conn:
            async def fetchval(self, sql: str, *params: object) -> int:
                return 42

        assert await _b().execute_scalar(_Conn()) == 42

    async def test_insert_execute_uses_execute_not_fetch(self) -> None:
        calls: list[str] = []

        class _Conn:
            async def fetch(self, sql: str, *params: object) -> list:
                calls.append("fetch")
                return []

            async def execute(self, sql: str, *params: object) -> str:
                calls.append("execute")
                return "INSERT 0 1"

        result = await _b().insert({"a": 1}).execute(_Conn())
        assert result == "INSERT 0 1"
        assert calls == ["execute"]


class TestModeSwitching:
    def test_select_after_insert_switches_mode(self) -> None:
        b = _b().insert({"a": 1})
        assert b.build().sql.startswith("INSERT")
        b.select("id")
        assert b.build().sql.startswith("SELECT")

    def test_data_reset_across_modes(self) -> None:
        b = _b().insert({"a": 1}).update({"b": 2}).where("id", "=", 1)
        sql = b.build().sql
        assert sql.startswith("UPDATE")
        assert "b" in sql
        assert "a" not in sql
