"""Tests for field type specification parser."""

import pytest

from quadkit.cli.generators.field_parser import FieldSpec, parse_fields


class TestParseFields:
    def test_simple_field(self):
        fields = parse_fields("name:str")
        assert len(fields) == 1
        assert fields[0].name == "name"
        assert fields[0].type == "str"
        assert fields[0].required is True

    def test_optional_field(self):
        fields = parse_fields("age:int?")
        assert fields[0].required is False

    def test_unique_constraint(self):
        fields = parse_fields("email:str!unique")
        assert fields[0].unique is True

    def test_foreign_key(self):
        fields = parse_fields("owner_id:int!fk=users.id")
        assert fields[0].fk == "users.id"

    def test_default_value(self):
        fields = parse_fields("created_at:datetime=now")
        assert fields[0].default == "now"

    def test_multiple_fields(self):
        fields = parse_fields("name:str,age:int?,email:str!unique")
        assert len(fields) == 3

    def test_enum_type(self):
        fields = parse_fields("status:enum=active,inactive")
        assert fields[0].type == "enum"

    def test_empty_string(self):
        fields = parse_fields("")
        assert fields == []
