"""Tests for ParserRegistry."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.parsers.csv import CSVOutputParser
from quadkit.ai.llm.parsers.json import JSONOutputParser
from quadkit.ai.llm.parsers.registry import ParserRegistry


class TestParserRegistry:
    """Test cases for ParserRegistry."""

    def test_register_and_get(self) -> None:
        """Test registering and retrieving a parser."""
        registry = ParserRegistry()
        parser = JSONOutputParser()
        registry.register("json", parser)
        assert registry.get("json") is parser

    def test_get_unknown_raises_error(self) -> None:
        """Test that getting unknown parser raises KeyError."""
        registry = ParserRegistry()
        with pytest.raises(KeyError) as exc_info:
            registry.get("unknown")
        assert "unknown" in str(exc_info.value)

    def test_get_or_none(self) -> None:
        """Test get_or_none returns None for unknown."""
        registry = ParserRegistry()
        assert registry.get_or_none("unknown") is None

    def test_list_parsers(self) -> None:
        """Test listing registered parsers."""
        registry = ParserRegistry()
        registry.register("json", JSONOutputParser())
        registry.register("csv", CSVOutputParser())
        parsers = registry.list_parsers()
        assert "json" in parsers
        assert "csv" in parsers

    def test_unregister(self) -> None:
        """Test unregistering a parser."""
        registry = ParserRegistry()
        registry.register("json", JSONOutputParser())
        registry.unregister("json")
        assert registry.get_or_none("json") is None

    def test_with_defaults(self) -> None:
        """Test with_defaults creates registry with defaults."""
        registry = ParserRegistry.with_defaults()
        parsers = registry.list_parsers()
        assert "json" in parsers
        assert "csv" in parsers
        assert "enum" in parsers
        assert "pydantic" in parsers
