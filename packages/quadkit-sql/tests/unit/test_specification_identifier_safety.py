"""Identifier safety tests for built-in SQL specifications (F7)."""

from __future__ import annotations

from typing import Any

import pytest

from quadkit.contracts.data import InvalidIdentifierError
from quadkit.sql.specification import (
    FieldBetween,
    FieldEquals,
    FieldGreaterThan,
    FieldIn,
    FieldIsNotNull,
    FieldIsNull,
    FieldLessThan,
    FieldLike,
    RawSpecification,
)

PAYLOAD = "id; DROP TABLE users;--"

FIELD_CLASSES: list[tuple[type[Any], list[Any]]] = [
    (FieldEquals, [PAYLOAD, 1]),
    (FieldIn, [PAYLOAD, [1, 2]]),
    (FieldBetween, [PAYLOAD, 1, 2]),
    (FieldLike, [PAYLOAD, "%a%"]),
    (FieldIsNull, [PAYLOAD]),
    (FieldIsNotNull, [PAYLOAD]),
    (FieldGreaterThan, [PAYLOAD, 1]),
    (FieldLessThan, [PAYLOAD, 1]),
]


@pytest.mark.parametrize(("cls", "args"), FIELD_CLASSES)
def test_field_class_rejects_payload_identifier(
    cls: type[Any], args: list[Any]
) -> None:
    """Every Field* class must reject a non-identifier field at construction."""
    with pytest.raises(InvalidIdentifierError):
        cls(*args)


def test_field_equals_quotes_column() -> None:
    """FieldEquals renders the field as a quoted column."""
    sql, params = FieldEquals("status", "active").to_sql()
    assert sql == '"status" = ?'
    assert params == ["active"]


def test_field_in_quotes_column() -> None:
    """FieldIn renders the field as a quoted column."""
    sql, params = FieldIn("id", [1, 2]).to_sql()
    assert sql == '"id" IN (?, ?)'
    assert params == [1, 2]


def test_field_between_quotes_column() -> None:
    """FieldBetween renders the field as a quoted column."""
    sql, params = FieldBetween("age", 18, 65).to_sql()
    assert sql == '"age" BETWEEN ? AND ?'
    assert params == [18, 65]


def test_composed_spec_quotes_columns() -> None:
    """AND-composed specs quote both fields."""
    sql, params = (FieldEquals("a", 1) & FieldEquals("b", 2)).to_sql()
    assert sql == '("a" = ?) AND ("b" = ?)'
    assert params == [1, 2]


def test_raw_spec_passthrough_unchanged() -> None:
    """RawSpecification is intentionally raw, but parameters stay bound."""
    sql, params = RawSpecification("id = ?", [5]).to_sql()
    assert sql == "id = ?"
    assert params == [5]
