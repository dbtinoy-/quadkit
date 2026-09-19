"""Tests for serialization/schema module."""

from __future__ import annotations

from dataclasses import MISSING
from typing import Any

from quadkit.serialization.schema.schema import (
    build_json_schema,
    python_type_to_json_schema,
)


class TestPythonTypeToJsonSchema:
    """Tests for python_type_to_json_schema function."""

    def test_string_type(self) -> None:
        """Test string type maps to string."""
        assert python_type_to_json_schema(str) == "string"

    def test_int_type(self) -> None:
        """Test int type maps to integer."""
        assert python_type_to_json_schema(int) == "integer"

    def test_float_type(self) -> None:
        """Test float type maps to number."""
        assert python_type_to_json_schema(float) == "number"

    def test_bool_type(self) -> None:
        """Test bool type maps to boolean."""
        assert python_type_to_json_schema(bool) == "boolean"

    def test_list_type(self) -> None:
        """Test list type maps to array."""
        assert python_type_to_json_schema(list) == "array"

    def test_dict_type(self) -> None:
        """Test dict type maps to object."""
        assert python_type_to_json_schema(dict) == "object"

    def test_optional_string(self) -> None:
        """Test Optional[str] maps to string."""
        result = python_type_to_json_schema(str | None)
        assert result == "string"

    def test_list_with_type_param(self) -> None:
        """Test list[str] maps to array."""
        result = python_type_to_json_schema(list[str])
        assert result == "array"

    def test_dict_with_type_params(self) -> None:
        """Test dict maps to object."""
        result = python_type_to_json_schema(dict[str, int])
        assert result == "object"

    def test_unknown_type_defaults_to_string(self) -> None:
        """Test unknown type defaults to string."""
        assert python_type_to_json_schema(SomeCustomClass) == "string"


class TestBuildJsonSchema:
    """Tests for build_json_schema function."""

    def test_empty_model(self) -> None:
        """Test empty model produces empty schema."""
        schema = build_json_schema({}, {})
        assert schema["type"] == "object"
        assert schema["properties"] == {}
        assert schema["required"] == []

    def test_single_field_no_default(self) -> None:
        """Test required field is marked in schema."""
        annotations = {"name": str}
        dc_fields = {"name": _make_field(default=MISSING)}
        schema = build_json_schema(annotations, dc_fields)
        assert "name" in schema["required"]
        assert schema["properties"]["name"]["type"] == "string"

    def test_single_field_with_default(self) -> None:
        """Test optional field is not marked as required."""
        annotations = {"name": str}
        dc_fields = {"name": _make_field(default="default")}
        schema = build_json_schema(annotations, dc_fields)
        assert "name" not in schema["required"]

    def test_multiple_fields(self) -> None:
        """Test multiple fields are all included."""
        annotations = {"name": str, "age": int, "active": bool}
        dc_fields = {
            "name": _make_field(default=MISSING),
            "age": _make_field(default=MISSING),
            "active": _make_field(default=False),
        }
        schema = build_json_schema(annotations, dc_fields)
        assert "name" in schema["properties"]
        assert "age" in schema["properties"]
        assert "active" in schema["properties"]
        assert "name" in schema["required"]
        assert "age" in schema["required"]
        assert "active" not in schema["required"]

    def test_field_type_mapping(self) -> None:
        """Test different types map to correct JSON schema types."""
        annotations = {
            "string_field": str,
            "int_field": int,
            "float_field": float,
            "bool_field": bool,
            "list_field": list,
        }
        dc_fields = {name: _make_field(default=None) for name in annotations}
        schema = build_json_schema(annotations, dc_fields)
        assert schema["properties"]["string_field"]["type"] == "string"
        assert schema["properties"]["int_field"]["type"] == "integer"
        assert schema["properties"]["float_field"]["type"] == "number"
        assert schema["properties"]["bool_field"]["type"] == "boolean"
        assert schema["properties"]["list_field"]["type"] == "array"

    def test_field_not_in_dc_fields(self) -> None:
        """Test field with no dc_field entry is still included."""
        annotations = {"name": str}
        dc_fields: dict[str, Any] = {}
        schema = build_json_schema(annotations, dc_fields)
        assert "name" in schema["properties"]


# Test helpers
class SomeCustomClass:
    """Custom class for testing unknown types."""


def _make_field(default: Any = MISSING, default_factory: Any = MISSING) -> Any:
    """Create a mock dataclass field."""

    class MockField:
        def __init__(self) -> None:
            self.default = default if default is not MISSING else MISSING
            self.default_factory = (
                default_factory if default_factory is not MISSING else MISSING
            )

    return MockField()
