"""Tests for EnumOutputParser."""

from __future__ import annotations

from enum import Enum

import pytest

from quadkit.ai.llm.parsers.enum import EnumOutputParser
from quadkit.ai.llm.structured.exceptions import ParseError


class Status(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


class TestEnumOutputParser:
    """Test cases for EnumOutputParser."""

    def test_parse_valid_enum_string(self) -> None:
        """Test parsing valid enum string."""
        parser = EnumOutputParser(Status)
        result = parser.parse('"active"')
        assert result == Status.ACTIVE

    def test_parse_invalid_enum_raises_error(self) -> None:
        """Test that invalid enum value raises ParseError."""
        parser = EnumOutputParser(Status)
        secret = "ENUM_PARSER_SECRET_SENTINEL"
        with pytest.raises(ParseError) as exc_info:
            parser.parse(f'"{secret}"')
        assert "Invalid enum value" in str(exc_info.value)
        assert secret not in str(exc_info.value)
        assert secret not in repr(exc_info.value.to_dict())
        assert exc_info.value.__context__ is None

    def test_parse_non_string_raises_error(self) -> None:
        """Test that non-string/non-int raises ParseError."""
        parser = EnumOutputParser(Status)
        with pytest.raises(ParseError):
            parser.parse("[1, 2, 3]")

    def test_get_format_instructions(self) -> None:
        """Test format instructions are returned."""
        parser = EnumOutputParser(Status)
        instructions = parser.get_format_instructions()
        assert "active" in instructions
        assert "inactive" in instructions
