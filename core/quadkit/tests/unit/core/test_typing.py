"""Tests for core/typing module - type hint resolution utilities."""

import pytest
from typing import Any, Optional, Union, List, Dict, ClassVar

from quadkit.primitives.typing import (
    type_allows_none,
    is_classvar,
    unwrap_optional,
    get_list_element_type,
    get_dict_value_type,
    EntityID,
    T,
)


class TestTypeAllowsNone:
    """Tests for type_allows_none function."""

    def test_none_type(self) -> None:
        """Test None type itself."""
        # type(None) is the type of None
        assert type_allows_none(type(None)) is True
        # Note: type_allows_none(None) returns False because it checks hint is type(None)
        # but None is the value, not the type
        assert type_allows_none(None) is False

    def test_optional_syntax(self) -> None:
        """Test Optional[X] syntax."""
        assert type_allows_none(Optional[str]) is True
        assert type_allows_none(Optional[int]) is True
        assert type_allows_none(Optional[dict]) is True

    def test_union_syntax(self) -> None:
        """Test Union[X, None] syntax."""
        assert type_allows_none(Union[str, None]) is True
        assert type_allows_none(Union[int, None]) is True

    def test_union_multiple(self) -> None:
        """Test Union with multiple types including None."""
        assert type_allows_none(Union[str, int, None]) is True

    def test_union_without_none(self) -> None:
        """Test Union without None."""
        assert type_allows_none(Union[str, int]) is False

    def test_plain_type(self) -> None:
        """Test plain type without Optional."""
        assert type_allows_none(str) is False
        assert type_allows_none(int) is False
        assert type_allows_none(dict) is False

    def test_python_310_union_syntax(self) -> None:
        """Test Python 3.10+ X | None syntax."""
        # This is types.UnionType which is only available in Python 3.10+
        result = str | None
        assert type_allows_none(result) is True
        
        result2 = int | None
        assert type_allows_none(result2) is True

    def test_plain_union_type(self) -> None:
        """Test plain union type without None."""
        result = str | int
        assert type_allows_none(result) is False


class TestIsClassvar:
    """Tests for is_classvar function."""

    def test_classvar_type(self) -> None:
        """Test ClassVar type."""
        assert is_classvar(ClassVar[int]) is True
        assert is_classvar(ClassVar[str]) is True

    def test_classvar_string(self) -> None:
        """Test string annotation containing ClassVar."""
        assert is_classvar("ClassVar[int]") is True
        assert is_classvar("ClassVar[str]") is True
        assert is_classvar("Optional[ClassVar[int]]") is True

    def test_regular_type(self) -> None:
        """Test regular type is not ClassVar."""
        assert is_classvar(int) is False
        assert is_classvar(str) is False
        assert is_classvar(dict) is False

    def test_optional_not_classvar(self) -> None:
        """Test Optional is not ClassVar."""
        assert is_classvar(Optional[int]) is False


class TestUnwrapOptional:
    """Tests for unwrap_optional function."""

    def test_optional(self) -> None:
        """Test unwrapping Optional."""
        assert unwrap_optional(Optional[str]) is str
        assert unwrap_optional(Optional[int]) is int

    def test_union_with_none(self) -> None:
        """Test unwrapping Union[X, None]."""
        assert unwrap_optional(Union[str, None]) is str
        assert unwrap_optional(Union[int, None]) is int

    def test_union_multiple(self) -> None:
        """Test Union with multiple types."""
        # Union[str, int, None] unwraps to Union[str, int] which is complex
        result = unwrap_optional(Union[str, int, None])
        # Should return Union[str, int]
        assert result != str  # Not a single type

    def test_non_optional(self) -> None:
        """Test non-optional type returns as-is."""
        assert unwrap_optional(str) is str
        assert unwrap_optional(int) is int
        assert unwrap_optional(dict) is dict

    def test_python_310_union(self) -> None:
        """Test Python 3.10+ union syntax."""
        result = str | None
        assert unwrap_optional(result) is str
        
        result2 = int | None
        assert unwrap_optional(result2) is int


class TestGetListElementType:
    """Tests for get_list_element_type function."""

    def test_list_with_type(self) -> None:
        """Test list[T] returns element type."""
        assert get_list_element_type(List[str]) is str
        assert get_list_element_type(List[int]) is int

    def test_list_without_type(self) -> None:
        """Test list without type parameter."""
        # In practice, just 'list' without []
        assert get_list_element_type(list) is None

    def test_non_list_type(self) -> None:
        """Test non-list type returns None."""
        assert get_list_element_type(str) is None
        assert get_list_element_type(int) is None
        assert get_list_element_type(dict) is None


class TestGetDictValueType:
    """Tests for get_dict_value_type function."""

    def test_dict_with_types(self) -> None:
        """Test dict[K, V] returns value type."""
        assert get_dict_value_type(Dict[str, int]) is int
        assert get_dict_value_type(Dict[str, str]) is str

    def test_dict_without_types(self) -> None:
        """Test dict without type parameters."""
        assert get_dict_value_type(dict) is None

    def test_non_dict_type(self) -> None:
        """Test non-dict type returns None."""
        assert get_dict_value_type(str) is None
        assert get_dict_value_type(list) is None


class TestTypeVars:
    """Tests for type aliases."""

    def test_entity_id_typevar(self) -> None:
        """Test EntityID TypeVar exists."""
        assert EntityID is not None

    def test_generic_typevar(self) -> None:
        """Test generic T TypeVar exists."""
        assert T is not None
