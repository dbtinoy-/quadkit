"""Tests for mapping module."""

from quadkit.mapping import MappingModule


class TestMappingModule:
    def test_mapping_module_exists(self) -> None:
        assert MappingModule is not None
