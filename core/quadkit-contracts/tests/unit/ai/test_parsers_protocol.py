"""Tests for Output Parser contracts (G-04 parity)."""
from __future__ import annotations


def test_json_parser():
    """JSONOutputParser should parse JSON responses."""
    from quadkit.contracts.ai.parsers import JSONOutputParser
    
    parser = JSONOutputParser()
    result = parser.parse('{"name": "Alice", "age": 30}')
    assert result["name"] == "Alice"
    assert result["age"] == 30


def test_xml_parser():
    """XMLOutputParser should parse XML responses."""
    from quadkit.contracts.ai.parsers import XMLOutputParser
    
    parser = XMLOutputParser()
    result = parser.parse('<person><name>Bob</name></person>')
    assert "Bob" in str(result)


def test_pydantic_parser():
    """PydanticOutputParser should parse into Pydantic model."""
    from quadkit.contracts.ai.parsers import PydanticOutputParser
    from pydantic import BaseModel
    
    class Person(BaseModel):
        name: str
        age: int
    
    parser = PydanticOutputParser(Person)
    result = parser.parse('{"name": "Carol", "age": 25}')
    assert isinstance(result, Person)
    assert result.name == "Carol"


def test_parser_get_format_instructions():
    """Parser should provide format instructions."""
    from quadkit.contracts.ai.parsers import JSONOutputParser
    
    parser = JSONOutputParser()
    instructions = parser.get_format_instructions()
    assert "json" in instructions.lower()
