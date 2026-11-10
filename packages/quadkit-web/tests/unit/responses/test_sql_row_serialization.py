"""SQL timestamp restoration is explicit, field-scoped and non-mutating."""

from datetime import date, datetime

import pytest

from quadkit.contracts.exceptions import SerializationError
from quadkit.serialization.domain import json_serialize
from quadkit.web.responses.sql import serialize_sql_row


@pytest.mark.parametrize(
    "value",
    [
        "2030-06-15 00:30:45.123456",
        "2030-06-15T00:30:45.123456Z",
        "2030-06-15T09:30:45.123456+09:00",
        "2030-06-14T19:30:45.123456-05:00",
        datetime(2030, 6, 15, 0, 30, 45, 123456),
        datetime.fromisoformat("2030-06-15T09:30:45.123456+09:00"),
    ],
)
def test_declared_datetime_restores_utc_without_touching_strings(value):
    details = {"timestamp": "2030-06-15 00:30:45.123456"}
    row = {"stamp": value, "title": "not-a-date", "details": details}
    result = serialize_sql_row(row, datetime_fields=("stamp",))
    assert result == {
        "stamp": "2030-06-15T00:30:45.123456+00:00",
        "title": "not-a-date",
        "details": details,
    }
    assert row["stamp"] == value
    assert row["details"] is details
    assert result["details"] is not details


@pytest.mark.parametrize(
    "value", ["", "not-a-date", "2030-06-15", 123, True, {}, date(2030, 6, 15)]
)
def test_invalid_stored_datetime_fails_closed(value):
    row = {"stamp": value}
    with pytest.raises(SerializationError, match="Invalid SQL datetime field: stamp"):
        serialize_sql_row(row, datetime_fields=("stamp",))
    assert row["stamp"] == value


def test_missing_and_nullable_fields_are_preserved():
    assert serialize_sql_row({"stamp": None}, datetime_fields=("stamp", "missing")) == {
        "stamp": None
    }


def test_undeclared_strings_and_generic_serializer_do_not_gain_timezone_policy():
    value = "2030-06-15 00:30:45"
    assert serialize_sql_row({"title": value}, datetime_fields=()) == {"title": value}
    assert json_serialize({"stamp": value}) == {"stamp": value}


def test_native_repository_plain_attr_entity_uses_the_same_boundary():
    class Row:
        def __init__(self):
            self.stamp = "2030-06-15 00:30:45"
            self.title = "not-a-date"

    row = Row()
    assert serialize_sql_row(row, datetime_fields=("stamp",)) == {
        "stamp": "2030-06-15T00:30:45+00:00",
        "title": "not-a-date",
    }
    assert row.stamp == "2030-06-15 00:30:45"
