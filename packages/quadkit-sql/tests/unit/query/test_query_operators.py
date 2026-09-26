"""Tests for query builder operator handlers and the operator registry."""

from __future__ import annotations

from quadkit.sql.query.operators import (
    BetweenOperator,
    EqualityOperator,
    GreaterThanOperator,
    GreaterThanOrEqualOperator,
    ILikeOperator,
    InOperator,
    IsNotNullOperator,
    IsNullOperator,
    LessThanOperator,
    LessThanOrEqualOperator,
    LikeOperator,
    NotBetweenOperator,
    NotEqualOperator,
    NotInOperator,
    Operator,
    QueryOperatorRegistry,
)


class TestComparisonHandlers:
    def test_equality(self) -> None:
        sql, params, next_idx = EqualityOperator().apply("name", "x", 1)
        assert sql == "name = $1"
        assert params == ["x"]
        assert next_idx == 2

    def test_not_equal(self) -> None:
        sql, params, next_idx = NotEqualOperator().apply("status", "off", 0)
        assert (sql, params, next_idx) == ("status != $0", ["off"], 1)

    def test_less_than(self) -> None:
        sql, _, idx = LessThanOperator().apply("age", 10, 2)
        assert (sql, idx) == ("age < $2", 3)

    def test_less_or_equal(self) -> None:
        sql, _, idx = LessThanOrEqualOperator().apply("age", 10, 2)
        assert (sql, idx) == ("age <= $2", 3)

    def test_greater_than(self) -> None:
        sql, _, idx = GreaterThanOperator().apply("age", 10, 2)
        assert (sql, idx) == ("age > $2", 3)

    def test_greater_or_equal(self) -> None:
        sql, _, idx = GreaterThanOrEqualOperator().apply("age", 10, 2)
        assert (sql, idx) == ("age >= $2", 3)

    def test_like(self) -> None:
        sql, params, idx = LikeOperator().apply("name", "%a%", 0)
        assert (sql, params, idx) == ("name LIKE $0", ["%a%"], 1)

    def test_ilike(self) -> None:
        sql, params, idx = ILikeOperator().apply("name", "%a%", 0)
        assert (sql, params, idx) == ("name ILIKE $0", ["%a%"], 1)

    def test_is_null_ignores_value_and_index(self) -> None:
        sql, params, idx = IsNullOperator().apply("deleted_at", None, 5)
        assert (sql, params, idx) == ("deleted_at IS NULL", [], 5)

    def test_is_not_null(self) -> None:
        sql, params, idx = IsNotNullOperator().apply("deleted_at", None, 5)
        assert (sql, params, idx) == ("deleted_at IS NOT NULL", [], 5)


class TestInHandlers:
    def test_in_multiple(self) -> None:
        sql, params, idx = InOperator().apply("id", [1, 2, 3], 0)
        assert sql == "id IN ($0, $1, $2)"
        assert params == [1, 2, 3]
        assert idx == 3

    def test_in_single(self) -> None:
        sql, params, idx = InOperator().apply("id", ["a"], 4)
        assert (sql, params, idx) == ("id IN ($4)", ["a"], 5)

    def test_in_empty_is_false(self) -> None:
        sql, params, idx = InOperator().apply("id", [], 0)
        # Empty IN list is unsatisfiable — 1=0 with no params.
        assert (sql, params, idx) == ("1=0", [], 0)

    def test_not_in_multiple(self) -> None:
        sql, params, idx = NotInOperator().apply("id", [9, 8], 1)
        assert (sql, params, idx) == ("id NOT IN ($1, $2)", [9, 8], 3)

    def test_not_in_empty_is_true(self) -> None:
        sql, params, idx = NotInOperator().apply("id", [], 1)
        # Empty NOT IN list is always true — 1=1.
        assert (sql, params, idx) == ("1=1", [], 1)

    def test_in_accepts_tuples(self) -> None:
        sql, params, idx = InOperator().apply("id", (1, 2), 0)
        assert (sql, params, idx) == ("id IN ($0, $1)", [1, 2], 2)


class TestBetweenHandlers:
    def test_between(self) -> None:
        sql, params, idx = BetweenOperator().apply("age", (18, 65), 3)
        assert (sql, params, idx) == ("age BETWEEN $3 AND $4", [18, 65], 5)

    def test_not_between(self) -> None:
        sql, params, idx = NotBetweenOperator().apply("age", (18, 65), 0)
        assert (sql, params, idx) == ("age NOT BETWEEN $0 AND $1", [18, 65], 2)


class TestOperatorEnum:
    def test_values(self) -> None:
        assert Operator.EQ.value == "="
        assert Operator.NE.value == "!="
        assert Operator.LT.value == "<"
        assert Operator.LE.value == "<="
        assert Operator.GT.value == ">"
        assert Operator.GE.value == ">="
        assert Operator.IN.value == "IN"
        assert Operator.NOT_IN.value == "NOT IN"
        assert Operator.LIKE.value == "LIKE"
        assert Operator.ILIKE.value == "ILIKE"
        assert Operator.IS_NULL.value == "IS NULL"
        assert Operator.IS_NOT_NULL.value == "IS NOT NULL"
        assert Operator.BETWEEN.value == "BETWEEN"
        assert Operator.NOT_BETWEEN.value == "NOT BETWEEN"

    def test_str_enum(self) -> None:
        assert f"{Operator.EQ}" == "="


class TestRegistry:
    def test_all_default_operators_registered(self) -> None:
        reg = QueryOperatorRegistry()
        # BETWEEN/NOT BETWEEN expect a 2-tuple value; the rest take any value.
        values = {
            Operator.BETWEEN: (1, 2),
            Operator.NOT_BETWEEN: (1, 2),
        }
        for op in Operator:
            value = values.get(op, "v")
            sql, _, idx = reg.apply_operator(op, "c", value, 0)
            # Every operator produces SQL and advances (or holds) the index.
            assert isinstance(sql, str)
            assert sql
            assert isinstance(idx, int)

    def test_apply_specific_operator(self) -> None:
        reg = QueryOperatorRegistry()
        sql, params, idx = reg.apply_operator(Operator.GT, "age", 21, 0)
        assert (sql, params, idx) == ("age > $0", [21], 1)

    def test_unknown_operator_falls_back_to_equality(self) -> None:
        # Remove an operator to exercise the fallback path.
        reg = QueryOperatorRegistry()
        del reg._operators[Operator.LIKE]  # noqa: SLF001
        sql, params, idx = reg.apply_operator(Operator.LIKE, "c", "v", 7)
        assert (sql, params, idx) == ("c = $7", ["v"], 8)

    def test_register_custom_operator(self) -> None:
        reg = QueryOperatorRegistry()

        class PrefixOp:
            def apply(self, column: str, value: object, param_idx: int):
                return (f"{column} LIKE ${param_idx}", [value], param_idx + 1)

        reg.register_operator(Operator.LIKE, PrefixOp())
        sql, _, _ = reg.apply_operator(Operator.LIKE, "name", "a%", 0)
        assert sql == "name LIKE $0"
