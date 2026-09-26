"""Tests for the filter expression compiler (PredicateCompiler)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from quadkit.contracts.data import (
    AndExpr,
    FieldEq,
    FieldGt,
    FieldIn,
    FieldLt,
    NotExpr,
    OrExpr,
)
from quadkit.sql.exceptions import DataQueryError
from quadkit.sql.query.compiler import PredicateCompiler


@dataclass
class _User:
    name: str = "anon"
    age: int = 0
    status: str = "active"


def _u(**kw) -> _User:
    return _User(**kw)


@pytest.fixture
def compiler() -> PredicateCompiler:
    return PredicateCompiler()


class TestLeafPredicates:
    def test_field_eq(self, compiler: PredicateCompiler) -> None:
        pred = compiler.compile(FieldEq(field="status", value="active"))
        assert pred(_u(status="active")) is True
        assert pred(_u(status="off")) is False

    def test_field_eq_missing_attribute_is_none(self, compiler: PredicateCompiler) -> None:
        pred = compiler.compile(FieldEq(field="status", value=None))

        class _Bare:
            pass

        assert pred(_Bare()) is True  # getattr default None == None

    def test_field_gt(self, compiler: PredicateCompiler) -> None:
        pred = compiler.compile(FieldGt(field="age", value=18))
        assert pred(_u(age=19)) is True
        assert pred(_u(age=18)) is False
        assert pred(_u(age=0)) is False

    def test_field_lt(self, compiler: PredicateCompiler) -> None:
        pred = compiler.compile(FieldLt(field="age", value=65))
        assert pred(_u(age=64)) is True
        assert pred(_u(age=65)) is False

    def test_field_in(self, compiler: PredicateCompiler) -> None:
        pred = compiler.compile(FieldIn(field="status", values=("active", "trial")))
        assert pred(_u(status="active")) is True
        assert pred(_u(status="off")) is False

    def test_gt_missing_attribute_is_not_error(self, compiler: PredicateCompiler) -> None:
        pred = compiler.compile(FieldGt(field="nope", value=1))

        class _Bare:
            pass

        assert pred(_Bare()) is False  # None guard, not a TypeError


class TestCombinators:
    def test_and(self, compiler: PredicateCompiler) -> None:
        expr = AndExpr(
            left=FieldEq(field="status", value="active"),
            right=FieldGt(field="age", value=18),
        )
        pred = compiler.compile(expr)
        assert pred(_u(status="active", age=20)) is True
        assert pred(_u(status="active", age=10)) is False
        assert pred(_u(status="off", age=20)) is False

    def test_or(self, compiler: PredicateCompiler) -> None:
        expr = OrExpr(
            left=FieldEq(field="status", value="active"),
            right=FieldEq(field="status", value="trial"),
        )
        pred = compiler.compile(expr)
        assert pred(_u(status="trial")) is True
        assert pred(_u(status="off")) is False

    def test_not(self, compiler: PredicateCompiler) -> None:
        pred = compiler.compile(NotExpr(expr=FieldEq(field="status", value="active")))
        assert pred(_u(status="active")) is False
        assert pred(_u(status="off")) is True

    def test_nested(self, compiler: PredicateCompiler) -> None:
        expr = OrExpr(
            left=AndExpr(
                left=FieldEq(field="status", value="active"),
                right=FieldLt(field="age", value=18),
            ),
            right=NotExpr(expr=FieldEq(field="status", value="banned")),
        )
        pred = compiler.compile(expr)
        # young active -> and-branch true
        assert pred(_u(status="active", age=10)) is True
        # banned but older -> not-branch false, and-branch false
        assert pred(_u(status="banned", age=40)) is False
        # off, older -> not(banned) true
        assert pred(_u(status="off", age=40)) is True


class TestUnsupported:
    def test_unknown_expression_raises(self, compiler: PredicateCompiler) -> None:
        with pytest.raises(DataQueryError, match="Unsupported filter expression"):
            compiler.compile(object())  # type: ignore[arg-type]


class TestFilteringHelper:
    def test_list_comprehension_usage(self, compiler: PredicateCompiler) -> None:
        pred = compiler.compile(
            AndExpr(
                left=FieldEq(field="status", value="active"),
                right=FieldGt(field="age", value=18),
            ),
        )
        users = [
            _u(name="a", status="active", age=30),
            _u(name="b", status="active", age=12),
            _u(name="c", status="off", age=40),
        ]
        result = [u for u in users if pred(u)]
        assert [u.name for u in result] == ["a"]
