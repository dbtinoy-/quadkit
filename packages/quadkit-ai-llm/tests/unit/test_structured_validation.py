from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pytest

from quadkit.validation import Field
from quadkit.domain import DomainModel
from quadkit.ai.llm import (
    ParseError,
    ResponseFormatter,
    SchemaValidationError,
    StructuredOutputParser,
)
from quadkit.ai.llm.types import Completion


@dataclass(init=False)
class Person(DomainModel):
    name: str = Field(..., description="Full name")
    age: int = Field(..., gt=0, description="Age in years")
    email: str | None = Field(None, description="Email address")


class TestStructuredOutputParser:
    def test_parse_valid_json(self):
        parser = StructuredOutputParser(Person)
        completion = Completion(
            content='{"name": "Alice", "age": 30}',
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        person = parser.parse(completion)
        assert person.name == "Alice"
        assert person.age == 30

    def test_parse_with_optional_fields(self):
        parser = StructuredOutputParser(Person)
        completion = Completion(
            content='{"name": "Bob", "age": 25, "email": "bob@example.com"}',
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        person = parser.parse(completion)
        assert person.name == "Bob"
        assert person.age == 25
        assert person.email == "bob@example.com"

    def test_parse_from_code_block(self):
        parser = StructuredOutputParser(Person)
        completion = Completion(
            content="""```json
            {"name": "Charlie", "age": 35}
            ```""",
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        person = parser.parse(completion)
        assert person.name == "Charlie"
        assert person.age == 35

    def test_parse_missing_required_field_raises_error(self):
        parser = StructuredOutputParser(Person)
        completion = Completion(
            content='{"name": "Alice"}',
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        with pytest.raises(SchemaValidationError):
            parser.parse(completion)

    def test_parse_invalid_field_value_raises_error(self):
        parser = StructuredOutputParser(Person)
        completion = Completion(
            content='{"name": "Alice", "age": -5}',
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        with pytest.raises(SchemaValidationError):
            parser.parse(completion)

    def test_parse_array(self):
        parser = StructuredOutputParser(Person)
        completion = Completion(
            content="""[
                {"name": "Alice", "age": 30},
                {"name": "Bob", "age": 25}
            ]""",
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        people = parser.parse_array(completion)
        assert len(people) == 2
        assert people[0].name == "Alice"
        assert people[1].name == "Bob"

    def test_parse_array_from_code_block(self):
        parser = StructuredOutputParser(Person)
        completion = Completion(
            content="""```json
            [
                {"name": "Charlie", "age": 35}
            ]
            ```""",
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        people = parser.parse_array(completion)
        assert len(people) == 1
        assert people[0].name == "Charlie"

    def test_parse_array_non_array_raises_error(self):
        parser = StructuredOutputParser(Person)
        completion = Completion(
            content='{"name": "Alice", "age": 30}',
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        with pytest.raises(ParseError):
            parser.parse_array(completion)

    def test_get_json_schema(self):
        parser = StructuredOutputParser(Person)
        schema = parser.get_json_schema()
        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "age" in schema["properties"]

    def test_get_schema_prompt(self):
        parser = StructuredOutputParser(Person)
        prompt = parser.get_schema_prompt()
        assert "name" in prompt
        assert "age" in prompt
        assert "required" in prompt or "optional" in prompt

    def test_parse_non_strict_mode(self):
        parser = StructuredOutputParser(Person, strict=False)
        completion = Completion(
            content="Not valid JSON",
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        with pytest.raises(ParseError):
            parser.parse(completion)


class TestResponseFormatter:
    def test_to_json(self):
        formatter = ResponseFormatter()
        completion = Completion(
            content='{"key": "value"}',
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        result = formatter.to_json(completion)
        assert result == {"key": "value"}

    def test_to_string(self):
        formatter = ResponseFormatter()
        completion = Completion(
            content="  Hello World  ",
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        result = formatter.to_string(completion)
        assert result == "Hello World"

    def test_to_string_no_strip(self):
        formatter = ResponseFormatter()
        completion = Completion(
            content="  Hello  ",
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        result = formatter.to_string(completion, strip=False)
        assert result == "  Hello  "

    def test_to_int_pure_number(self):
        formatter = ResponseFormatter()
        completion = Completion(
            content="42",
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        result = formatter.to_int(completion)
        assert result == 42
        assert isinstance(result, int)

    def test_to_int_from_text(self):
        formatter = ResponseFormatter()
        completion = Completion(
            content="The answer is 42",
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        result = formatter.to_int(completion)
        assert result == 42

    def test_to_int_negative(self):
        formatter = ResponseFormatter()
        completion = Completion(
            content="-10",
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        result = formatter.to_int(completion)
        assert result == -10

    def test_to_int_invalid_raises_error(self):
        formatter = ResponseFormatter()
        completion = Completion(
            content="not a number",
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        with pytest.raises(ParseError):
            formatter.to_int(completion)

    def test_to_float_pure_number(self):
        formatter = ResponseFormatter()
        completion = Completion(
            content="3.14",
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        result = formatter.to_float(completion)
        assert result == 3.14
        assert isinstance(result, float)

    def test_to_float_from_text(self):
        formatter = ResponseFormatter()
        completion = Completion(
            content="The value is 3.14159",
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        result = formatter.to_float(completion)
        assert abs(result - 3.14159) < 0.0001

    def test_to_bool_true_variants(self):
        formatter = ResponseFormatter()

        for value in ["true", "True", "yes", "Yes", "1", "y", "Y"]:
            completion = Completion(
                content=value,
                model="mock",
                role="assistant",
                usage=None,
                timestamp=datetime.now(),
            )
            result = formatter.to_bool(completion)
            assert result is True

    def test_to_bool_false_variants(self):
        formatter = ResponseFormatter()

        for value in ["false", "False", "no", "No", "0", "n", "N"]:
            completion = Completion(
                content=value,
                model="mock",
                role="assistant",
                usage=None,
                timestamp=datetime.now(),
            )
            result = formatter.to_bool(completion)
            assert result is False

    def test_to_bool_invalid_raises_error(self):
        formatter = ResponseFormatter()
        completion = Completion(
            content="maybe",
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        with pytest.raises(ParseError):
            formatter.to_bool(completion)

    def test_to_list_newline_separated(self):
        formatter = ResponseFormatter()
        completion = Completion(
            content="Apple\nBanana\nCherry",
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        result = formatter.to_list(completion)
        assert result == ["Apple", "Banana", "Cherry"]

    def test_to_list_json_array(self):
        formatter = ResponseFormatter()
        completion = Completion(
            content='["Apple", "Banana", "Cherry"]',
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        result = formatter.to_list(completion)
        assert result == ["Apple", "Banana", "Cherry"]

    def test_to_list_custom_separator(self):
        formatter = ResponseFormatter()
        completion = Completion(
            content="Apple, Banana, Cherry",
            model="mock",
            role="assistant",
            usage=None,
            timestamp=datetime.now(),
        )
        result = formatter.to_list(completion, separator=", ")
        assert result == ["Apple", "Banana", "Cherry"]
