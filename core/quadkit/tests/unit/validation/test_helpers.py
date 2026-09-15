"""Tests for validation/helpers.py - Result-based validation helpers."""

import pytest

from quadkit.result import Ok, Err
from quadkit.validation.rules import (
    validate_required,
    validate_type,
    validate_range,
)


class TestValidateRequired:
    """Tests for validate_required function."""

    def test_valid_value(self) -> None:
        """Test validate_required returns Ok for non-None value."""
        result = validate_required("hello", "name")
        
        assert result.is_ok()
        assert result.unwrap() == "hello"

    def test_none_value(self) -> None:
        """Test validate_required returns Err for None."""
        result = validate_required(None, "name")
        
        assert result.is_err()
        assert isinstance(result.unwrap_err(), ValueError)
        assert "name is required" in str(result.unwrap_err())

    def test_zero_value(self) -> None:
        """Test validate_required returns Ok for zero (falsy but not None)."""
        result = validate_required(0, "count")
        
        assert result.is_ok()
        assert result.unwrap() == 0

    def test_empty_string(self) -> None:
        """Test validate_required returns Ok for empty string (not None)."""
        result = validate_required("", "name")
        
        assert result.is_ok()
        assert result.unwrap() == ""

    def test_false_value(self) -> None:
        """Test validate_required returns Ok for False."""
        result = validate_required(False, "flag")
        
        assert result.is_ok()
        assert result.unwrap() is False


class TestValidateType:
    """Tests for validate_type function."""

    def test_valid_type(self) -> None:
        """Test validate_type returns Ok for correct type."""
        result = validate_type("hello", str, "value")
        
        assert result.is_ok()
        assert result.unwrap() == "hello"

    def test_invalid_type(self) -> None:
        """Test validate_type returns Err for incorrect type."""
        result = validate_type(123, str, "value")
        
        assert result.is_err()
        assert isinstance(result.unwrap_err(), TypeError)
        assert "must be of type str" in str(result.unwrap_err())
        assert "got int" in str(result.unwrap_err())

    def test_subclass_type(self) -> None:
        """Test validate_type works with inheritance."""
        class Base:
            pass
        
        class Derived(Base):
            pass
        
        obj = Derived()
        result = validate_type(obj, Base, "value")
        
        assert result.is_ok()
        assert result.unwrap() is obj

    def test_custom_name(self) -> None:
        """Test validate_type uses custom name in error message."""
        result = validate_type(42, str, "age")
        
        assert result.is_err()
        assert "age" in str(result.unwrap_err())


class TestValidateRange:
    """Tests for validate_range function."""

    def test_within_range(self) -> None:
        """Test validate_range returns Ok when within bounds."""
        result = validate_range(5, min_value=0, max_value=10, name="value")
        
        assert result.is_ok()
        assert result.unwrap() == 5

    def test_at_min_boundary(self) -> None:
        """Test validate_range returns Ok at minimum boundary."""
        result = validate_range(0, min_value=0, max_value=10, name="value")
        
        assert result.is_ok()

    def test_at_max_boundary(self) -> None:
        """Test validate_range returns Ok at maximum boundary."""
        result = validate_range(10, min_value=0, max_value=10, name="value")
        
        assert result.is_ok()

    def test_below_min(self) -> None:
        """Test validate_range returns Err when below minimum."""
        result = validate_range(-1, min_value=0, max_value=10, name="value")
        
        assert result.is_err()
        assert isinstance(result.unwrap_err(), ValueError)
        assert "must be at least 0" in str(result.unwrap_err())

    def test_above_max(self) -> None:
        """Test validate_range returns Err when above maximum."""
        result = validate_range(11, min_value=0, max_value=10, name="value")
        
        assert result.is_err()
        assert isinstance(result.unwrap_err(), ValueError)
        assert "must be at most 10" in str(result.unwrap_err())

    def test_min_only(self) -> None:
        """Test validate_range with only min_value."""
        result = validate_range(5, min_value=0, name="value")
        
        assert result.is_ok()

    def test_max_only(self) -> None:
        """Test validate_range with only max_value."""
        result = validate_range(5, max_value=10, name="value")
        
        assert result.is_ok()

    def test_no_bounds(self) -> None:
        """Test validate_range with no bounds."""
        result = validate_range(100, name="value")
        
        assert result.is_ok()
        assert result.unwrap() == 100

    def test_custom_name_in_error(self) -> None:
        """Test validate_range uses custom name in error message."""
        result = validate_range(-5, min_value=0, max_value=10, name="age")
        
        assert result.is_err()
        assert "age" in str(result.unwrap_err())
