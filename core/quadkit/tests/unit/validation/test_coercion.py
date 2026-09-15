"""Tests for validation coercion module."""
import datetime
from enum import Enum
from uuid import UUID, uuid4

import pytest

from quadkit.validation.engine.coercion import (
    BOOL_FALSE,
    BOOL_TRUE,
    coerce_field_value,
    coerce_str_to_bool,
    coerce_to_bool,
)


class TestCoerceStrToBool:
    """Tests for coerce_str_to_bool function."""

    @pytest.mark.parametrize("val", BOOL_TRUE)
    def test_true_values(self, val: str) -> None:
        """Test that all truthy string values return True."""
        assert coerce_str_to_bool(val) is True

    @pytest.mark.parametrize("val", BOOL_FALSE)
    def test_false_values(self, val: str) -> None:
        """Test that all falsy string values return False."""
        assert coerce_str_to_bool(val) is False

    def test_case_insensitive(self) -> None:
        """Test that coercion is case insensitive."""
        assert coerce_str_to_bool("TRUE") is True
        assert coerce_str_to_bool("Yes") is True
        assert coerce_str_to_bool("NO") is False

    def test_strips_whitespace(self) -> None:
        """Test that whitespace is stripped."""
        assert coerce_str_to_bool("  true  ") is True
        assert coerce_str_to_bool("  yes  ") is True

    def test_invalid_value_raises(self) -> None:
        """Test that invalid values raise ValueError."""
        with pytest.raises(ValueError, match="Cannot coerce"):
            coerce_str_to_bool("invalid")

    def test_empty_string_raises(self) -> None:
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Cannot coerce"):
            coerce_str_to_bool("")


class TestCoerceToBool:
    """Tests for coerce_to_bool function."""

    def test_coerce_true_string(self) -> None:
        """Test coerce_to_bool with truthy string."""
        assert coerce_to_bool("true") is True

    def test_coerce_false_string(self) -> None:
        """Test coerce_to_bool with falsy string."""
        assert coerce_to_bool("false") is False

    def test_coerce_none(self) -> None:
        """Test coerce_to_bool with None."""
        assert coerce_to_bool(None) is False

    def test_coerce_int_positive(self) -> None:
        """Test coerce_to_bool with positive int."""
        assert coerce_to_bool(1) is True

    def test_coerce_int_zero(self) -> None:
        """Test coerce_to_bool with zero int."""
        assert coerce_to_bool(0) is False

    def test_coerce_empty_list(self) -> None:
        """Test coerce_to_bool with empty list."""
        assert coerce_to_bool([]) is False

    def test_coerce_non_empty_list(self) -> None:
        """Test coerce_to_bool with non-empty list."""
        assert coerce_to_bool([1]) is True


class Color(Enum):
    """Test enum."""
    RED = "red"
    GREEN = "green"
    BLUE = "blue"


class TestCoerceFieldValue:
    """Tests for coerce_field_value function."""

    def test_passthrough_none(self) -> None:
        """Test that None values pass through."""
        result = coerce_field_value("field", None, {}, None)
        assert result is None

    def test_passthrough_no_type_hint(self) -> None:
        """Test passthrough when no type hint."""
        result = coerce_field_value("field", "value", {}, None)
        assert result == "value"

    def test_coerce_uuid_from_string(self) -> None:
        """Test UUID coercion from string."""
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        result = coerce_field_value("id", uuid_str, {"id": UUID}, None)
        assert result == UUID(uuid_str)

    def test_coerce_uuid_preserves_uuid(self) -> None:
        """Test that UUID objects pass through."""
        original = uuid4()
        result = coerce_field_value("id", original, {"id": UUID}, None)
        assert result == original

    def test_coerce_datetime_from_string(self) -> None:
        """Test datetime coercion from ISO string."""
        dt_str = "2024-01-15T10:30:00"
        result = coerce_field_value(
            "created_at", dt_str, {"created_at": datetime.datetime}, None
        )
        assert result == datetime.datetime.fromisoformat(dt_str)

    def test_coerce_datetime_preserves_datetime(self) -> None:
        """Test that datetime objects pass through."""
        original = datetime.datetime.now()
        result = coerce_field_value(
            "created_at", original, {"created_at": datetime.datetime}, None
        )
        assert result == original

    def test_coerce_enum_from_string(self) -> None:
        """Test Enum coercion from string."""
        result = coerce_field_value("color", "red", {"color": Color}, None)
        assert result == Color.RED

    def test_coerce_enum_from_int(self) -> None:
        """Test Enum coercion from string value."""
        result = coerce_field_value("color", "red", {"color": Color}, None)
        assert result == Color.RED

    def test_coerce_enum_preserves_enum(self) -> None:
        """Test that Enum objects pass through."""
        original = Color.BLUE
        result = coerce_field_value("color", original, {"color": Color}, None)
        assert result == original

    def test_coerce_bool_from_string_true(self) -> None:
        """Test bool coercion from truthy string."""
        result = coerce_field_value("active", "true", {"active": bool}, None)
        assert result is True

    def test_coerce_bool_from_string_false(self) -> None:
        """Test bool coercion from falsy string."""
        result = coerce_field_value("active", "false", {"active": bool}, None)
        assert result is False

    def test_coerce_int_from_string(self) -> None:
        """Test int coercion from string."""
        result = coerce_field_value("count", "42", {"count": int}, None)
        assert result == 42

    def test_coerce_int_preserves_int(self) -> None:
        """Test that int objects pass through."""
        original = 100
        result = coerce_field_value("count", original, {"count": int}, None)
        assert result == original

    def test_coerce_float_from_string(self) -> None:
        """Test float coercion from string."""
        result = coerce_field_value("price", "3.14", {"price": float}, None)
        assert result == 3.14

    def test_coerce_float_preserves_float(self) -> None:
        """Test that float objects pass through."""
        original = 2.718
        result = coerce_field_value("price", original, {"price": float}, None)
        assert result == original

    def test_coerce_id_field_string_to_uuid(self) -> None:
        """Test special 'id' field coercion to UUID when type hint is present."""
        uuid_str = "550e8400-e29b-41d4-a716-446655440000"
        result = coerce_field_value("id", uuid_str, {"id": UUID}, None)
        assert result == UUID(uuid_str)

    def test_coerce_id_field_invalid_uuid_passthrough(self) -> None:
        """Test that invalid UUID strings for 'id' pass through."""
        result = coerce_field_value("id", "not-a-uuid", {}, None)
        assert result == "not-a-uuid"

    def test_list_coercion_preserves_list(self) -> None:
        """Test that lists pass through."""
        original = [1, 2, 3]
        result = coerce_field_value("items", original, {}, None)
        assert result == original

    def test_dict_coercion_preserves_dict(self) -> None:
        """Test that dicts pass through."""
        original = {"key": "value"}
        result = coerce_field_value("data", original, {}, None)
        assert result == original

    def test_non_type_passthrough(self) -> None:
        """Test passthrough for non-type hints."""
        result = coerce_field_value("field", "value", {"field": "not_a_type"}, None)
        assert result == "value"