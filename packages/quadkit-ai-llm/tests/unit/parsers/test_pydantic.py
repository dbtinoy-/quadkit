"""Tests for PydanticOutputParser."""

from __future__ import annotations

from pydantic import BaseModel
import pytest

from quadkit.ai.llm.parsers.pydantic import PydanticOutputParser
from quadkit.ai.llm.structured.exceptions import ParseError, SchemaValidationError


class User(BaseModel):
    name: str
    age: int


class TestPydanticOutputParser:
    """Test cases for PydanticOutputParser."""

    def test_parse_valid_pydantic(self) -> None:
        """Test parsing valid JSON into Pydantic model."""
        parser = PydanticOutputParser(User)
        result = parser.parse('{"name": "John", "age": 30}')
        assert result.name == "John"
        assert result.age == 30

    def test_parse_with_markdown_fence(self) -> None:
        """Test parsing JSON wrapped in markdown fence."""
        parser = PydanticOutputParser(User)
        result = parser.parse('```json\n{"name": "Jane", "age": 25}\n```')
        assert result.name == "Jane"
        assert result.age == 25

    def test_parse_invalid_json_raises_error(self) -> None:
        """Test that invalid JSON raises ParseError."""
        parser = PydanticOutputParser(User)
        with pytest.raises(ParseError):
            parser.parse("not valid json")

    def test_parse_invalid_schema_raises_error(self) -> None:
        """Test that validation failure raises SchemaValidationError."""
        parser = PydanticOutputParser(User)
        secret = "PYDANTIC_PARSER_SECRET_SENTINEL"
        with pytest.raises(SchemaValidationError) as exc_info:
            parser.parse(f'{{"name": "John", "age": "{secret}"}}')
        assert secret not in str(exc_info.value)
        assert secret not in repr(exc_info.value.to_dict())
        assert exc_info.value.__cause__ is None
        assert exc_info.value.__context__ is None

    def test_get_format_instructions(self) -> None:
        """Test format instructions are returned."""
        parser = PydanticOutputParser(User)
        instructions = parser.get_format_instructions()
        assert "JSON" in instructions
        assert "schema" in instructions.lower()
