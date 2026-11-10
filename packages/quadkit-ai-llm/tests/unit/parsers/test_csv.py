"""Tests for CSVOutputParser."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.parsers.csv import CSVOutputParser
from quadkit.ai.llm.structured.exceptions import ParseError


class TestCSVOutputParser:
    """Test cases for CSVOutputParser."""

    def test_parse_valid_csv(self) -> None:
        """Test parsing valid JSON array."""
        parser = CSVOutputParser()
        result = parser.parse('[{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]')
        assert len(result) == 2
        assert result[0]["name"] == "John"
        assert result[1]["age"] == 25

    def test_parse_not_array_raises_error(self) -> None:
        """Test that non-array raises ParseError."""
        parser = CSVOutputParser()
        with pytest.raises(ParseError) as exc_info:
            parser.parse('{"name": "John"}')
        assert "Expected JSON array" in str(exc_info.value)

    def test_parse_invalid_json_raises_error(self) -> None:
        """Test that invalid JSON raises ParseError."""
        parser = CSVOutputParser()
        with pytest.raises(ParseError):
            parser.parse("not valid json")

    def test_get_format_instructions(self) -> None:
        """Test format instructions are returned."""
        parser = CSVOutputParser()
        instructions = parser.get_format_instructions()
        assert "JSON" in instructions
        assert "array" in instructions.lower()
