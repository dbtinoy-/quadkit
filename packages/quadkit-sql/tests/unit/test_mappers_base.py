"""
Tests for mappers.base: MappingError, FieldMapping and DataMapper helpers
"""

import pytest

from quadkit.sql.mappers.base import DataMapper, FieldMapping, MappingError


def test_mapping_error_str_includes_details():
    err = MappingError("oops", entity_type="User", field_name="id", value=42)
    s = str(err)
    assert "oops" in s
    assert "entity_type=User" in s
    assert "field=id" in s
    assert "value=42" in s


def test_field_mapping_conversions():
    fm = FieldMapping(
        "created_at",
        "created_at",
        converter=lambda x: x + "Z",
        reverse_converter=lambda x: x[:-1],
    )

    assert fm.convert_to_entity("2020-01-01") == "2020-01-01Z"
    assert fm.convert_to_db("2020-01-01Z") == "2020-01-01"

    fm_no_conv = FieldMapping("name", "name")
    assert fm_no_conv.convert_to_entity("Alice") == "Alice"
    assert fm_no_conv.convert_to_db("Alice") == "Alice"


class BrokenMapper(DataMapper):
    def to_entity(self, row):
        if row == {"bad": True}:
            raise MappingError("bad row", entity_type="Broken")
        return {"ok": row}

    def to_row(self, entity):
        if entity == {"bad": True}:
            raise MappingError("bad entity", entity_type="Broken")
        return entity


def test_data_mapper_to_entities_wraps_errors():
    mapper = BrokenMapper(dict)
    with pytest.raises(MappingError) as exc:
        mapper.to_entities([{"ok": 1}, {"bad": True}, {"ok": 2}])

    assert "index 1" in exc.value.message or "index" in str(exc.value)


def test_data_mapper_to_rows_wraps_errors():
    mapper = BrokenMapper(dict)
    with pytest.raises(MappingError):
        mapper.to_rows([{"ok": 1}, {"bad": True}])


def test_validate_entity_and_row():
    mapper = BrokenMapper(dict)
    with pytest.raises(MappingError):
        mapper.validate_entity(123)  # not the expected type

    with pytest.raises(MappingError):
        mapper.validate_row(None)
