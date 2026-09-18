"""Tests for contracts/data/types.py — filter expressions and pagination specs."""

from __future__ import annotations

import pytest

from quadkit.contracts.data.types import (
    AndExpr,
    CursorPaginationSpec,
    FieldEq,
    FieldGt,
    FieldIn,
    FieldLt,
    NotExpr,
    OrExpr,
    PaginationSpec,
    ProjectionSpec,
    SortSpecification,
)


class TestFieldPredicates:
    """Tests for field predicate classes."""

    def test_field_eq_creation(self) -> None:
        """FieldEq creates correctly."""
        expr = FieldEq("status", "active")
        assert expr.field == "status"
        assert expr.value == "active"

    def test_field_eq_is_frozen(self) -> None:
        """FieldEq is frozen (immutable)."""
        expr = FieldEq("status", "active")
        with pytest.raises(AttributeError):
            expr.value = "inactive"

    def test_field_gt_creation(self) -> None:
        """FieldGt creates correctly."""
        expr = FieldGt("age", 18)
        assert expr.field == "age"
        assert expr.value == 18

    def test_field_gt_is_frozen(self) -> None:
        """FieldGt is frozen."""
        expr = FieldGt("age", 18)
        with pytest.raises(AttributeError):
            expr.value = 21

    def test_field_lt_creation(self) -> None:
        """FieldLt creates correctly."""
        expr = FieldLt("price", 100)
        assert expr.field == "price"
        assert expr.value == 100

    def test_field_lt_is_frozen(self) -> None:
        """FieldLt is frozen."""
        expr = FieldLt("price", 100)
        with pytest.raises(AttributeError):
            expr.value = 50

    def test_field_in_creation(self) -> None:
        """FieldIn creates correctly with tuple of values."""
        expr = FieldIn("status", ("active", "pending"))
        assert expr.field == "status"
        assert expr.values == ("active", "pending")

    def test_field_in_is_frozen(self) -> None:
        """FieldIn is frozen."""
        expr = FieldIn("status", ("a", "b"))
        with pytest.raises(AttributeError):
            expr.values = ("c",)


class TestLogicalExpressions:
    """Tests for logical expression classes."""

    def test_and_expr_creation(self) -> None:
        """AndExpr combines two expressions."""
        left = FieldEq("status", "active")
        right = FieldGt("age", 18)
        expr = AndExpr(left, right)
        assert expr.left is left
        assert expr.right is right

    def test_and_expr_is_frozen(self) -> None:
        """AndExpr is frozen."""
        expr = AndExpr(FieldEq("a", 1), FieldEq("b", 2))
        with pytest.raises(AttributeError):
            expr.left = FieldEq("c", 3)

    def test_or_expr_creation(self) -> None:
        """OrExpr combines two expressions."""
        left = FieldEq("status", "active")
        right = FieldEq("status", "pending")
        expr = OrExpr(left, right)
        assert expr.left is left
        assert expr.right is right

    def test_or_expr_is_frozen(self) -> None:
        """OrExpr is frozen."""
        expr = OrExpr(FieldEq("a", 1), FieldEq("b", 2))
        with pytest.raises(AttributeError):
            expr.left = FieldEq("c", 3)

    def test_not_expr_creation(self) -> None:
        """NotExpr negates an expression."""
        inner = FieldEq("status", "active")
        expr = NotExpr(inner)
        assert expr.expr is inner

    def test_not_expr_is_frozen(self) -> None:
        """NotExpr is frozen."""
        expr = NotExpr(FieldEq("a", 1))
        with pytest.raises(AttributeError):
            expr.expr = FieldEq("b", 2)

    def test_nested_expressions(self) -> None:
        """Expressions can be nested."""
        expr = AndExpr(
            OrExpr(FieldEq("a", 1), FieldEq("b", 2)),
            NotExpr(FieldEq("c", 3)),
        )
        assert isinstance(expr.left, OrExpr)
        assert isinstance(expr.right, NotExpr)


class TestSortSpecification:
    """Tests for SortSpecification."""

    def test_sort_spec_creation_default(self) -> None:
        """SortSpecification defaults to ascending."""
        spec = SortSpecification("name")
        assert spec.field == "name"
        assert spec.direction == "asc"

    def test_sort_spec_creation_desc(self) -> None:
        """SortSpecification can be descending."""
        spec = SortSpecification("created_at", "desc")
        assert spec.field == "created_at"
        assert spec.direction == "desc"

    def test_sort_spec_is_frozen(self) -> None:
        """SortSpecification is frozen."""
        spec = SortSpecification("name")
        with pytest.raises(AttributeError):
            spec.direction = "desc"


class TestPaginationSpec:
    """Tests for PaginationSpec."""

    def test_pagination_defaults(self) -> None:
        """PaginationSpec has sensible defaults."""
        spec = PaginationSpec()
        assert spec.page == 1
        assert spec.size == 20

    def test_pagination_custom_values(self) -> None:
        """PaginationSpec accepts custom values."""
        spec = PaginationSpec(page=3, size=50)
        assert spec.page == 3
        assert spec.size == 50

    def test_pagination_offset_calculation(self) -> None:
        """offset property calculates correctly."""
        spec = PaginationSpec(page=1, size=20)
        assert spec.offset == 0

        spec = PaginationSpec(page=2, size=20)
        assert spec.offset == 20

        spec = PaginationSpec(page=5, size=10)
        assert spec.offset == 40

    def test_pagination_is_frozen(self) -> None:
        """PaginationSpec is frozen."""
        spec = PaginationSpec()
        with pytest.raises(AttributeError):
            spec.page = 2


class TestCursorPaginationSpec:
    """Tests for CursorPaginationSpec."""

    def test_cursor_pagination_defaults(self) -> None:
        """CursorPaginationSpec has sensible defaults."""
        spec = CursorPaginationSpec()
        assert spec.cursor is None
        assert spec.size == 20

    def test_cursor_pagination_with_cursor(self) -> None:
        """CursorPaginationSpec accepts cursor string."""
        spec = CursorPaginationSpec(cursor="abc123", size=10)
        assert spec.cursor == "abc123"
        assert spec.size == 10

    def test_cursor_pagination_is_frozen(self) -> None:
        """CursorPaginationSpec is frozen."""
        spec = CursorPaginationSpec()
        with pytest.raises(AttributeError):
            spec.cursor = "new"


class TestProjectionSpec:
    """Tests for ProjectionSpec."""

    def test_projection_defaults(self) -> None:
        """ProjectionSpec defaults to include all fields."""
        spec = ProjectionSpec()
        assert spec.include == frozenset()
        assert spec.exclude == frozenset()

    def test_projection_with_include(self) -> None:
        """ProjectionSpec can specify included fields."""
        spec = ProjectionSpec(include={"id", "name"})
        assert spec.include == frozenset({"id", "name"})

    def test_projection_with_exclude(self) -> None:
        """ProjectionSpec can specify excluded fields."""
        spec = ProjectionSpec(exclude={"password", "token"})
        assert spec.exclude == frozenset({"password", "token"})

    def test_projection_both_include_and_exclude(self) -> None:
        """ProjectionSpec can have both include and exclude."""
        spec = ProjectionSpec(include={"id"}, exclude={"password"})
        assert spec.include == frozenset({"id"})
        assert spec.exclude == frozenset({"password"})

    def test_projection_is_frozen(self) -> None:
        """ProjectionSpec is frozen."""
        spec = ProjectionSpec()
        with pytest.raises(AttributeError):
            spec.include = {"new"}
