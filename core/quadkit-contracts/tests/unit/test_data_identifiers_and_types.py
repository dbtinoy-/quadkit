"""Data contracts: SQL identifiers (injection safety), filter/sort/pagination."""

from __future__ import annotations

import pytest

from quadkit.contracts.core.constants import (
    EP_MODULES,
    EP_PROVIDERS,
)
from quadkit.contracts.data.identifiers import (
    Column,
    Identifier,
    QualifiedTable,
    Schema,
    Table,
    column,
    schema,
    table,
    validate_identifier,
)
from quadkit.contracts.data.sql.sql import InvalidIdentifierError
from quadkit.contracts.data.sql.sql_dialect import SQLDialect
from quadkit.contracts.data.types import (
    AndExpr,
    CursorPaginationSpec,
    FieldEq,
    FieldGt,
    FieldIn,
    FieldLt,
    LogicalOperator,
    NotExpr,
    OrExpr,
    PaginationSpec,
    ProjectionSpec,
    SortSpecification,
)


class TestIdentifierValidation:
    def test_valid_names(self) -> None:
        for name in ["users", "_priv", "col1", "A_9"]:
            ident = Identifier(name)
            assert ident.name == name
            assert ident.quoted == f'"{name}"'
            assert str(ident) == f'"{name}"'

    def test_empty_rejected(self) -> None:
        with pytest.raises(InvalidIdentifierError):
            Identifier("")

    @pytest.mark.parametrize(
        "name",
        ["1abc", "drop; --", "a b", "a-b", "a.b", "SELECT 1", "a; DROP TABLE x"],
    )
    def test_injection_rejected(self, name: str) -> None:
        with pytest.raises(InvalidIdentifierError):
            Identifier(name)

    def test_length_limit(self) -> None:
        long_name = "a" * 64  # postgres max is 63
        with pytest.raises(InvalidIdentifierError, match="maximum length"):
            Identifier(long_name)
        assert Identifier("a" * 63).name == "a" * 63

    def test_mysql_quoting_and_length(self) -> None:
        ident = Identifier("users", dialect=SQLDialect.MYSQL)
        assert ident.quoted == "`users`"
        assert ident.dialect is SQLDialect.MYSQL
        assert Identifier("a" * 64, dialect=SQLDialect.MYSQL).name == "a" * 64

    def test_reserved_detection(self) -> None:
        t = Table("SELECT")  # valid characters; reserved-ness is advisory
        assert t.is_reserved
        assert not Table("users").is_reserved

    def test_equality_and_hash(self) -> None:
        a, b = Table("users"), Table("users")
        assert a == b
        assert hash(a) == hash(b)
        assert Table("users") != Column("users")  # different concrete types
        assert Table("users") != Table("orders")
        assert Table("users") != "users"


class TestFactoriesAndQualified:
    def test_factories_cached(self) -> None:
        assert table("t1") is table("t1")
        assert column("c1") is column("c1")
        assert schema("s1") is schema("s1")

    def test_qualified_table(self) -> None:
        qt = QualifiedTable(Schema("public"), Table("users"))
        assert qt.quoted == '"public"."users"'
        assert str(qt) == '"public"."users"'
        assert qt.schema.name == "public"
        assert qt.table.name == "users"
        assert qt == QualifiedTable(Schema("public"), Table("users"))
        assert qt != QualifiedTable(Schema("other"), Table("users"))

    def test_validate_identifier(self) -> None:
        assert validate_identifier("ok_name") == "ok_name"
        with pytest.raises(InvalidIdentifierError):
            validate_identifier("bad name")


class TestFilterExpressions:
    def test_leaf_predicates(self) -> None:
        assert FieldEq("a", 1) == FieldEq("a", 1)
        assert FieldGt("a", 1) != FieldLt("a", 1)
        assert FieldIn("a", (1, 2)).values == (1, 2)

    def test_composition(self) -> None:
        expr = AndExpr(FieldEq("status", "active"), FieldGt("age", 18))
        assert expr.left.field == "status"
        assert expr.right.value == 18
        nested = OrExpr(expr, NotExpr(FieldEq("banned", True)))
        assert isinstance(nested.left, AndExpr)
        assert isinstance(nested.right, NotExpr)
        assert LogicalOperator.AND == "and"
        assert LogicalOperator.OR == "or"

    def test_frozen(self) -> None:
        import dataclasses

        e = FieldEq("a", 1)
        with pytest.raises(dataclasses.FrozenInstanceError):
            e.value = 2  # type: ignore[misc]


class TestSortPaginationProjection:
    def test_sort(self) -> None:
        assert SortSpecification("name").direction == "asc"
        assert SortSpecification("name", "desc").direction == "desc"

    def test_offset_pagination(self) -> None:
        assert PaginationSpec().offset == 0
        assert PaginationSpec(page=2, size=10).offset == 10
        assert PaginationSpec(page=3).size == 20

    def test_cursor_pagination(self) -> None:
        c = CursorPaginationSpec(cursor="abc", size=5)
        assert c.cursor == "abc"
        assert c.size == 5
        assert CursorPaginationSpec().cursor is None

    def test_projection(self) -> None:
        p = ProjectionSpec(include=frozenset({"a"}), exclude=frozenset({"b"}))
        assert p.include == frozenset({"a"})
        assert p.exclude == frozenset({"b"})
        assert ProjectionSpec().include == frozenset()


class TestContractsConstants:
    def test_entry_point_groups(self) -> None:
        assert EP_PROVIDERS == "quadkit.providers"
        assert EP_MODULES == "quadkit.modules"
