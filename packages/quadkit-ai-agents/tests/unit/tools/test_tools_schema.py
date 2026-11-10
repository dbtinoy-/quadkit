from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

import pytest

from quadkit.ai.agents.tools import tool, generate_json_schema


class Status(Enum):
    ACTIVE = "active"
    ERROR = "error"


class TestGenerateJsonSchema:
    def test_generate_from_function(self) -> None:
        def my_function(name: str, age: int, active: bool = True) -> dict:
            """A test function."""
            return {}

        schema = generate_json_schema(my_function)

        assert schema["type"] == "object"
        assert "name" in schema["properties"]
        assert "age" in schema["properties"]
        assert "active" in schema["properties"]
        assert "name" in schema["required"]
        assert "age" in schema["required"]

    def test_generate_with_typed_parameters(self) -> None:
        def typed_function(items: list[str], mapping: dict[str, int]) -> None:
            """Typed function."""
            pass

        schema = generate_json_schema(typed_function)

        assert schema["properties"]["items"]["type"] == "array"
        assert schema["properties"]["mapping"]["type"] == "object"

    def test_generate_preserves_optional(self) -> None:
        def optional_params(required: str, optional: str = "default") -> None:
            """Test function."""
            pass

        schema = generate_json_schema(optional_params)

        assert "required" in schema
        assert "required" in schema["required"]
        assert "optional" not in schema["required"]

    def test_generate_infers_descriptions_from_docstring(self) -> None:
        def described_function(query: str, max_results: int = 10) -> list:
            """Search for items.

            Args:
                query: The search query to execute.
                max_results: Maximum number of results to return.

            Returns:
                A list of matching items.
            """
            return []

        schema = generate_json_schema(described_function)

        assert schema["properties"]["query"]["description"] == "The search query to execute."
        assert schema["properties"]["max_results"]["description"] == "Maximum number of results to return."

    def test_generate_no_description_without_docstring(self) -> None:
        def no_doc(name: str) -> None:
            pass

        schema = generate_json_schema(no_doc)

        assert "description" not in schema["properties"]["name"]

    def test_generate_optional_nullable_schema(self) -> None:
        def nullable_param(value: str | None = None) -> None:
            """Function with nullable param."""
            pass

        schema = generate_json_schema(nullable_param)

        prop = schema["properties"]["value"]
        assert prop["nullable"] is True
        assert prop["type"] == "string"

    def test_generate_list_items_schema(self) -> None:
        def list_param(tags: list[str]) -> None:
            """Function with list param."""
            pass

        schema = generate_json_schema(list_param)

        prop = schema["properties"]["tags"]
        assert prop["type"] == "array"
        assert prop["items"]["type"] == "string"

    def test_generate_manual_schema_takes_precedence_via_decorator(self) -> None:
        @tool
        async def fetch_url(url: str) -> str:
            """Fetch content from a URL.

            Args:
                url: The URL to fetch.
            """
            return ""

        assert fetch_url.parameters_schema["properties"]["url"]["type"] == "string"
        assert fetch_url.parameters_schema["properties"]["url"]["description"] == "The URL to fetch."

    def test_generate_literal_schema(self) -> None:
        def literal_param(mode: Literal["fast", "slow", "balanced"]) -> None:
            pass

        schema = generate_json_schema(literal_param)
        prop = schema["properties"]["mode"]
        assert prop["type"] == "string"
        assert prop["enum"] == ["fast", "slow", "balanced"]

    def test_generate_enum_schema(self) -> None:
        def enum_param(status: Status) -> None:
            pass

        schema = generate_json_schema(enum_param)
        prop = schema["properties"]["status"]
        assert prop["type"] == "string"
        assert set(prop["enum"]) == {"active", "error"}

    def test_generate_annotated_schema(self) -> None:
        def annotated_param(count: Annotated[int, "Some metadata"]) -> None:
            pass

        schema = generate_json_schema(annotated_param)
        prop = schema["properties"]["count"]
        assert prop["type"] == "integer"
