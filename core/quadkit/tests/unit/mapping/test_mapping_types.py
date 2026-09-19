"""Unit tests for quadkit-mapping types."""

from quadkit.mapping.types import D, MappingFn, S


class TestMappingTypes:
    """Tests for mapping type definitions."""

    def test_typevar_s(self) -> None:
        """Test S TypeVar."""
        # TypeVars don't have runtime values, but we can verify they exist
        assert S is not None

    def test_typevar_d(self) -> None:
        """Test D TypeVar."""
        # TypeVars don't have runtime values, but we can verify they exist
        assert D is not None

    def test_typevars_are_different(self) -> None:
        """Test that S and D are different TypeVars."""
        assert S is not D

    def test_mapping_fn_type_alias(self) -> None:
        """Test MappingFn type alias."""

        def my_mapper(source: str) -> int:
            return len(source)

        # Verify the function matches the type alias
        mapping_fn: MappingFn = my_mapper
        assert mapping_fn("hello") == 5

    def test_mapping_fn_with_different_types(self) -> None:
        """Test MappingFn with different source/destination types."""

        def str_to_upper(source: str) -> str:
            return source.upper()

        def str_to_len(source: str) -> int:
            return len(source)

        mapping_fn_upper: MappingFn = str_to_upper
        mapping_fn_len: MappingFn = str_to_len

        assert mapping_fn_upper("hello") == "HELLO"
        assert mapping_fn_len("hello") == 5


class TestMappingTypesExports:
    """Tests for mapping types module exports."""

    def test_all_exports(self) -> None:
        """Test that all types are properly exported."""
        from quadkit.mapping import types

        expected = ["D", "MappingFn", "S"]
        for name in expected:
            assert hasattr(types, name)
