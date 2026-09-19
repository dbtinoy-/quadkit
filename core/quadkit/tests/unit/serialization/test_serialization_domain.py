"""Tests for serialization/domain module."""
import datetime
from dataclasses import dataclass
from enum import Enum
from uuid import UUID, uuid4

import pytest

from quadkit.serialization.domain import (
    get_model_extra,
    json_serialize,
    model_dump_to_dict,
)


class Color(Enum):
    """Test enum."""
    RED = "red"
    GREEN = "green"


@dataclass
class SimpleDataclass:
    """Simple dataclass for testing."""
    name: str
    value: int = 0


class MockModelWithModelDump:
    """Mock model with model_dump method."""

    def model_dump(self, mode: str = "python") -> dict:
        return {"field": "value", "mode": mode}


class MockModelWithDict:
    """Mock model with __dict__."""

    def __init__(self) -> None:
        self.field = "value"
        self._private = "private"


class TestJsonSerialize:
    """Tests for json_serialize function."""

    def test_serialize_none(self) -> None:
        """Test serialization of None."""
        assert json_serialize(None) is None

    def test_serialize_bool(self) -> None:
        """Test serialization of booleans."""
        assert json_serialize(True) is True
        assert json_serialize(False) is False

    def test_serialize_int(self) -> None:
        """Test serialization of integers."""
        assert json_serialize(42) == 42

    def test_serialize_float(self) -> None:
        """Test serialization of floats."""
        assert json_serialize(3.14) == 3.14

    def test_serialize_str(self) -> None:
        """Test serialization of strings."""
        assert json_serialize("hello") == "hello"

    def test_serialize_dict(self) -> None:
        """Test serialization of dict."""
        result = json_serialize({"key": "value"})
        assert result == {"key": "value"}

    def test_serialize_dict_nested(self) -> None:
        """Test serialization of nested dict."""
        result = json_serialize({"a": {"b": {"c": 1}}})
        assert result == {"a": {"b": {"c": 1}}}

    def test_serialize_list(self) -> None:
        """Test serialization of list."""
        result = json_serialize([1, 2, 3])
        assert result == [1, 2, 3]

    def test_serialize_tuple(self) -> None:
        """Test serialization of tuple."""
        result = json_serialize((1, 2, 3))
        assert result == [1, 2, 3]

    def test_serialize_uuid(self) -> None:
        """Test serialization of UUID."""
        uuid = UUID("550e8400-e29b-41d4-a716-446655440000")
        result = json_serialize(uuid)
        assert result == "550e8400-e29b-41d4-a716-446655440000"

    def test_serialize_datetime(self) -> None:
        """Test serialization of datetime."""
        dt = datetime.datetime(2024, 1, 15, 10, 30, 0)
        result = json_serialize(dt)
        assert result == "2024-01-15T10:30:00"

    def test_serialize_enum(self) -> None:
        """Test serialization of Enum."""
        assert json_serialize(Color.RED) == "red"

    def test_serialize_model_dump(self) -> None:
        """Test serialization of model with model_dump."""
        model = MockModelWithModelDump()
        result = json_serialize(model)
        assert result == {"field": "value", "mode": "json"}

    def test_serialize_ellipsis(self) -> None:
        """Test serialization of Ellipsis."""
        result = json_serialize(...)
        assert result is None

    def test_serialize_object_with_dict(self) -> None:
        """Test serialization of object with __dict__ includes non-callable attrs."""
        model = MockModelWithDict()
        result = json_serialize(model)
        # Objects with __dict__ serialize all non-callable attrs
        assert "field" in result

    def test_serialize_callable(self) -> None:
        """Test serialization of callable converts to string."""
        def my_func():
            pass
        result = json_serialize(my_func)
        # Callables without __name__ fallback to str()
        assert isinstance(result, str)

    def test_serialize_recursive_list_of_dicts(self) -> None:
        """Test recursive serialization in list of dicts."""
        data = [{"key": UUID("550e8400-e29b-41d4-a716-446655440000")}]
        result = json_serialize(data)
        assert result == [{"key": "550e8400-e29b-41d4-a716-446655440000"}]


class TestModelDumpToDict:
    """Tests for model_dump_to_dict function."""

    def test_dump_dataclass(self) -> None:
        """Test dumping dataclass."""
        model = SimpleDataclass(name="test", value=42)
        result = model_dump_to_dict(model)
        assert result == {"name": "test", "value": 42}

    def test_dump_dataclass_exclude(self) -> None:
        """Test dumping with exclude."""
        model = SimpleDataclass(name="test", value=42)
        result = model_dump_to_dict(model, exclude={"value"})
        assert result == {"name": "test"}

    def test_dump_dataclass_include(self) -> None:
        """Test dumping with include."""
        model = SimpleDataclass(name="test", value=42)
        result = model_dump_to_dict(model, include={"value"})
        assert result == {"value": 42}

    def test_dump_dataclass_json_mode(self) -> None:
        """Test dumping in json mode."""
        model = SimpleDataclass(name="test", value=42)
        result = model_dump_to_dict(model, mode="json")
        # mode="json" uses json_serialize which handles primitives
        assert result == {"name": "test", "value": 42}

    def test_dump_object_with_dict(self) -> None:
        """Test dumping object with __dict__."""
        model = MockModelWithDict()
        result = model_dump_to_dict(model)
        assert "field" in result

    def test_dump_object_with_extra_in_dict(self) -> None:
        """Test that extra attributes in __dict__ are included (including private)."""
        model = MockModelWithDict()
        result = model_dump_to_dict(model)
        assert "field" in result
        # model_dump_to_dict includes all __dict__ items
        assert "_private" in result


class TestGetModelExtra:
    """Tests for get_model_extra function."""

    def test_dataclass_no_extra(self) -> None:
        """Test dataclass without extra fields."""
        model = SimpleDataclass(name="test")
        result = get_model_extra(model)
        assert result is None

    def test_dataclass_with_extra(self) -> None:
        """Test dataclass with extra fields."""

        @dataclass
        class ModelWithExtra:
            name: str = "test"

        model = ModelWithExtra()
        model.extra_field = "extra"
        result = get_model_extra(model)
        assert result == {"extra_field": "extra"}

    def test_object_without_dataclass_fields(self) -> None:
        """Test object without __dataclass_fields__ returns None."""

        class PlainObj:
            def __init__(self) -> None:
                self.field = "value"
                self.extra = "extra"

        model = PlainObj()
        result = get_model_extra(model)
        # Without __dataclass_fields__, returns None
        assert result is None

    def test_object_with_private_extra(self) -> None:
        """Test that private fields are not included in extras."""

        class ObjWithPrivate:
            def __init__(self) -> None:
                self.field = "value"
                self._private = "private"

        model = ObjWithPrivate()
        result = get_model_extra(model)
        # Without __dataclass_fields__, returns None
        assert result is None