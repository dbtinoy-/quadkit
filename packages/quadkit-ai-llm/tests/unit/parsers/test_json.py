"""Tests for JSONOutputParser."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.parsers.json import JSONOutputParser
from quadkit.ai.llm.structured.exceptions import ParseError


class TestJSONOutputParser:
    """Test cases for JSONOutputParser."""

    def test_parse_valid_json(self) -> None:
        """Test parsing valid JSON string."""
        parser = JSONOutputParser()
        result = parser.parse('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_with_markdown_fence(self) -> None:
        """Test parsing JSON wrapped in markdown code fence."""
        parser = JSONOutputParser()
        result = parser.parse('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_parse_json_with_plain_fence(self) -> None:
        """Test parsing JSON wrapped in plain markdown fence."""
        parser = JSONOutputParser()
        result = parser.parse('```\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_parse_invalid_json_raises_error(self) -> None:
        """Test that invalid JSON raises ParseError."""
        parser = JSONOutputParser()
        secret = "JSON_PARSER_SECRET_SENTINEL"
        with pytest.raises(ParseError) as exc_info:
            parser.parse(f'{{"value": "{secret}", invalid}}')
        assert secret not in str(exc_info.value)
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__context__ is None

    def test_get_format_instructions(self) -> None:
        """Test format instructions are returned."""
        parser = JSONOutputParser()
        instructions = parser.get_format_instructions()
        assert "JSON" in instructions
        assert len(instructions) > 0
