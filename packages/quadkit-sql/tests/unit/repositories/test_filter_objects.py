"""Tests for typed SQL filter value objects (F, Filter, helpers)."""

from __future__ import annotations

import pytest

from quadkit.sql.repositories.filter_objects import (
    F,
    Filter,
    ensure_filter,
    field,
    normalize_filters,
)


class TestFieldResolution:
    def test_string_reference(self) -> None:
        assert field("email").field_name == "email"

    def test_name_attribute(self) -> None:
        class _Ref:
            name = "full_name"

        assert field(_Ref()).field_name == "full_name"

    def test_field_name_attribute(self) -> None:
        class _Ref:
            field_name = "fk"

        assert field(_Ref()).field_name == "fk"

    def test_unresolvable_raises(self) -> None:
        with pytest.raises(TypeError, match="Cannot resolve SQL field name"):
            field(42)

    def test_empty_string_rejected(self) -> None:
        with pytest.raises(TypeError, match="Cannot resolve"):
            field("")


class TestComparisons:
    def test_eq(self) -> None:
        sql, params = (F("status") == "active").to_sql()
        assert (sql, params) == ('"status" = ?', ["active"])

    def test_eq_none_is_is_null(self) -> None:
        sql, params = (F("deleted_at") == None).to_sql()  # noqa: E711
        assert (sql, params) == ('"deleted_at" IS NULL', [])

    def test_ne(self) -> None:
        sql, params = (F("status") != "off").to_sql()
        assert (sql, params) == ('"status" != ?', ["off"])

    def test_ne_none_is_is_not_null(self) -> None:
        sql, params = (F("deleted_at") != None).to_sql()  # noqa: E711
        assert (sql, params) == ('"deleted_at" IS NOT NULL', [])

    def test_gt_lt_gte_lte(self) -> None:
        assert (F("age") > 21).to_sql() == ('"age" > ?', [21])
        assert (F("age") < 65).to_sql() == ('"age" < ?', [65])
        assert (F("age") >= 21).to_sql() == ('"age" >= ?', [21])
        assert (F("age") <= 65).to_sql() == ('"age" <= ?', [65])


class TestSetOperations:
    def test_in(self) -> None:
        sql, params = F("id").in_([1, 2, 3]).to_sql()
        assert (sql, params) == ('"id" IN (?, ?, ?)', [1, 2, 3])

    def test_in_empty(self) -> None:
        sql, params = F("id").in_([]).to_sql()
        assert (sql, params) == ("1 = 0", [])

    def test_not_in(self) -> None:
        sql, params = F("id").not_in([9]).to_sql()
        assert (sql, params) == ('"id" NOT IN (?)', [9])

    def test_not_in_empty(self) -> None:
        sql, params = F("id").not_in(()).to_sql()
        assert (sql, params) == ("1 = 1", [])

    def test_like_ilike_contains(self) -> None:
        assert F("name").like("%a%").to_sql() == ('"name" LIKE ?', ["%a%"])
        assert F("name").ilike("%a%").to_sql() == ('"name" ILIKE ?', ["%a%"])
        assert F("name").contains("mid").to_sql() == ('"name" LIKE ?', ["%mid%"])

    def test_is_null_is_not_null(self) -> None:
        assert F("x").is_null().to_sql() == ('"x" IS NULL', [])
        assert F("x").is_not_null().to_sql() == ('"x" IS NOT NULL', [])

    def test_between(self) -> None:
        sql, params = F("age").between(18, 65).to_sql()
        assert (sql, params) == ('"age" BETWEEN ? AND ?', [18, 65])


class TestComposition:
    def test_and(self) -> None:
        f = (F("a") == 1) & (F("b") == 2)
        sql, params = f.to_sql()
        assert sql == '("a" = ? AND "b" = ?)'
        assert params == [1, 2]

    def test_or(self) -> None:
        f = (F("a") == 1) | (F("b") == 2)
        sql, params = f.to_sql()
        assert sql == '("a" = ? OR "b" = ?)'
        assert params == [1, 2]

    def test_invert(self) -> None:
        f = ~(F("a") == 1)
        sql, params = f.to_sql()
        assert sql == 'NOT ("a" = ?)'
        assert params == [1]

    def test_nested_composition(self) -> None:
        f = ((F("a") == 1) & (F("b") > 2)) | (F("c").is_null())
        sql, params = f.to_sql()
        assert sql == '(("a" = ? AND "b" > ?) OR "c" IS NULL)'
        assert params == [1, 2]

    def test_chained_and(self) -> None:
        f = (F("a") == 1) & (F("b") == 2) & (F("c") == 3)
        sql, params = f.to_sql()
        assert "AND" in sql
        assert params == [1, 2, 3]


class TestFilterValidation:
    def test_predicate_missing_field_raises(self) -> None:
        with pytest.raises(ValueError, match="field_name and operator"):
            Filter(kind="predicate", operator="eq", value=1).to_sql()

    def test_predicate_missing_operator_raises(self) -> None:
        with pytest.raises(ValueError, match="field_name and operator"):
            Filter(kind="predicate", field_name="a").to_sql()

    def test_unsupported_operator_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported filter operator"):
            Filter(kind="predicate", field_name="a", operator="regex", value="x").to_sql()

    def test_frozen(self) -> None:
        import dataclasses

        f = Filter(kind="predicate", field_name="a", operator="eq", value=1)
        with pytest.raises(dataclasses.FrozenInstanceError):
            f.value = 2  # type: ignore[misc]

    def test_ensure_filter_passthrough(self) -> None:
        f = F("a") == 1
        assert ensure_filter(f) is f

    def test_ensure_filter_rejects_other(self) -> None:
        with pytest.raises(TypeError, match="Expected Filter"):
            ensure_filter("not a filter")

    def test_normalize_filters(self) -> None:
        f1, f2 = F("a") == 1, F("b") == 2
        assert normalize_filters([f1, f2]) == [f1, f2]

    def test_normalize_filters_rejects(self) -> None:
        with pytest.raises(TypeError):
            normalize_filters([F("a") == 1, "bad"])

    def test_and_coerces_non_filter(self) -> None:
        with pytest.raises(TypeError, match="Expected Filter"):
            (F("a") == 1) & "raw"  # type: ignore[operator]


class TestColumnQuoting:
    def test_column_names_are_quoted(self) -> None:
        sql, _ = (F("full_name") == 1).to_sql()
        assert sql.startswith('"full_name"')

    def test_invalid_identifier_rejected(self) -> None:
        from quadkit.contracts.data.sql.sql import InvalidIdentifierError

        with pytest.raises(InvalidIdentifierError):
            (F("user-name") == 1).to_sql()  # hyphen is not a valid SQL identifier
