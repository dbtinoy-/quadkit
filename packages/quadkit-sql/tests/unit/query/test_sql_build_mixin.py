"""Tests for the AsyncQueryBuilder build path (_BuildMixin + _WhereMixin):
SELECT/INSERT/UPDATE/DELETE construction and WHERE assembly.

These exercise the mixin through the public fluent API of
:class:`AsyncQueryBuilder`, which is how the mixin is consumed.
"""

from __future__ import annotations

import pytest

from quadkit.sql.query.operators import Operator
from quadkit.sql.query.sql_builder import AsyncQueryBuilder


def _b(table: str = "users") -> AsyncQueryBuilder:
    return AsyncQueryBuilder(table)


class TestSelectBuild:
    def test_select_all(self) -> None:
        q = _b().build()
        assert q.sql == 'SELECT * FROM "users"'
        assert q.params == ()

    def test_select_columns_where_order_limit(self) -> None:
        q = (
            _b()
            .select("id", "email")
            .where("status", Operator.EQ, "active")
            .order_by("created_at", desc=True)
            .limit(10)
            .build()
        )
        assert (
            q.sql
            == 'SELECT "id", "email" FROM "users" WHERE "status" = $1 '
            'ORDER BY "created_at" DESC LIMIT $2'
        )
        assert q.params == ("active", 10)

    def test_offset(self) -> None:
        q = _b().limit(10).offset(20).build()
        assert q.sql.endswith("LIMIT $1 OFFSET $2")
        assert q.params == (10, 20)

    def test_default_mode_is_select(self) -> None:
        # A freshly constructed builder defaults to SELECT mode.
        q = _b().build()
        assert q.sql == 'SELECT * FROM "users"'
        # An explicitly unknown mode raises.
        b = _b()
        b._mode = "bogus"  # noqa: SLF001
        with pytest.raises(ValueError, match="Unknown query mode"):
            b.build()


class TestWhereAssembly:
    def test_multiple_where_and_joined(self) -> None:
        q = (
            _b()
            .where("status", "=", "active")
            .where("age", ">", 21)
            .build()
        )
        assert 'WHERE "status" = $1 AND "age" > $2' in q.sql
        assert q.params == ("active", 21)

    def test_where_in(self) -> None:
        q = _b().where("id", Operator.IN, [1, 2, 3]).build()
        assert "IN ($1, $2, $3)" in q.sql
        assert q.params == (1, 2, 3)

    def test_where_in_empty(self) -> None:
        q = _b().where("id", Operator.IN, []).build()
        assert "1=0" in q.sql
        assert q.params == ()

    def test_where_is_null(self) -> None:
        q = _b().where("deleted_at", Operator.IS_NULL).build()
        assert "IS NULL" in q.sql
        assert q.params == ()

    def test_where_between(self) -> None:
        q = _b().where_between("age", 18, 65).build()
        assert "BETWEEN $1 AND $2" in q.sql
        assert q.params == (18, 65)

    def test_where_not_between(self) -> None:
        q = _b().where_not_between("age", 18, 65).build()
        assert "NOT BETWEEN $1 AND $2" in q.sql
        assert q.params == (18, 65)

    def test_where_if_skipped_when_false(self) -> None:
        q = _b().where_if(False, "status", "=", "x").build()
        assert "WHERE" not in q.sql

    def test_where_if_applied_when_true(self) -> None:
        q = _b().where_if(True, "status", "=", "x").build()
        assert 'WHERE "status" = $1' in q.sql

    def test_where_exists(self) -> None:
        q = _b().where_exists('SELECT 1 FROM "orders"').build()
        assert "EXISTS" in q.sql
        assert "SELECT 1 FROM" in q.sql

    def test_where_not_exists(self) -> None:
        q = _b().where_not_exists('SELECT 1 FROM "orders"').build()
        assert "NOT EXISTS" in q.sql

    def test_where_raw(self) -> None:
        # Raw expressions are pass-through: the placeholder stays as the
        # caller wrote it (documented escape hatch), params are collected.
        q = _b().where_raw('"id" > ?', [5]).build()
        assert '"id" > ?' in q.sql
        assert q.params == (5,)


class TestInsertBuild:
    def test_insert(self) -> None:
        q = _b().insert({"email": "a@x", "name": "a"}).build()
        assert q.sql.startswith('INSERT INTO "users"')
        assert '"email"' in q.sql
        assert '"name"' in q.sql
        assert q.params == ("a@x", "a")

    def test_insert_empty_data(self) -> None:
        # Documented behavior: empty data builds a column-less insert.
        q = _b().insert({}).build()
        assert q.sql == 'INSERT INTO "users" () VALUES ()'
        assert q.params == ()


class TestUpdateBuild:
    def test_update_with_where(self) -> None:
        q = (
            _b()
            .update({"name": "new"})
            .where("id", "=", 1)
            .build()
        )
        assert q.sql.startswith('UPDATE "users" SET')
        assert 'WHERE "id" = $2' in q.sql
        assert q.params == ("new", 1)

    def test_update_without_where_rejected(self) -> None:
        with pytest.raises(ValueError, match="WHERE"):
            _b().update({"name": "new"}).build()


class TestDeleteBuild:
    def test_delete_with_where(self) -> None:
        q = _b().delete().where("id", "=", 9).build()
        assert q.sql.startswith('DELETE FROM "users"')
        assert 'WHERE "id" = $1' in q.sql
        assert q.params == (9,)

    def test_delete_without_where_rejected(self) -> None:
        with pytest.raises(ValueError, match="WHERE"):
            _b().delete().build()
