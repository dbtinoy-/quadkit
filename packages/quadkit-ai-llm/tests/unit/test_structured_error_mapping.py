from __future__ import annotations

from dataclasses import dataclass

import pytest

from quadkit.validation import Field
from quadkit.domain import DomainModel
from quadkit.ai.llm import (
    StructuredOutputError,
    ParseError,
    SchemaValidationError,
    complete_with_json,
    complete_with_schema,
    create_json_mode_messages,
)
from support.mock_clients import MockLLMClient


@dataclass(init=False)
class Person(DomainModel):
    name: str = Field(..., description="Full name")
    age: int = Field(..., gt=0, description="Age in years")
    email: str | None = Field(None, description="Email address")


class TestHelperFunctions:
    def test_create_json_mode_messages_basic(self):
        messages = create_json_mode_messages("Test prompt")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "JSON" in messages[0]["content"]
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Test prompt"

    def test_create_json_mode_messages_with_schema(self):
        messages = create_json_mode_messages("Extract person", schema=Person)
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "name" in messages[1]["content"]
        assert "age" in messages[1]["content"]

    def test_create_json_mode_messages_custom_system(self):
        custom = "Custom system prompt"
        messages = create_json_mode_messages("Test", system_prompt=custom)
        assert messages[0]["content"] == custom

    @pytest.mark.asyncio
    async def test_complete_with_schema(self):
        client = MockLLMClient()

        original_complete = client.complete

        async def mock_complete(messages, **kwargs):
            from quadkit.result import Ok
            completion = (await original_complete(messages, **kwargs)).unwrap()
            completion.content = '{"name": "Alice", "age": 30}'
            return Ok(completion)

        client.complete = mock_complete

        person = await complete_with_schema(client, "Extract person", schema=Person)
        assert person.name == "Alice"
        assert person.age == 30

    @pytest.mark.asyncio
    async def test_complete_with_json(self):
        client = MockLLMClient()

        original_complete = client.complete

        async def mock_complete(messages, **kwargs):
            from quadkit.result import Ok
            completion = (await original_complete(messages, **kwargs)).unwrap()
            completion.content = '{"status": "ok", "count": 5}'
            return Ok(completion)

        client.complete = mock_complete

        data = await complete_with_json(client, "Generate data")
        assert data == {"status": "ok", "count": 5}


class TestErrorHierarchy:
    def test_structured_output_error_base(self):
        error = StructuredOutputError("Test error")
        assert "Test error" in str(error)
        assert isinstance(error, Exception)

    def test_parse_error_inheritance(self):
        error = ParseError("Parse failed")
        assert isinstance(error, StructuredOutputError)
        assert isinstance(error, Exception)

    def test_validation_error_inheritance(self):
        error = SchemaValidationError("Validation failed")
        assert isinstance(error, StructuredOutputError)
        assert isinstance(error, Exception)
