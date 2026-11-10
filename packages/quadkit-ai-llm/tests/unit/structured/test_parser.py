"""Unit tests for quadkit.ai.llm.structured.parser."""

from __future__ import annotations

import dataclasses
from typing import Literal

import pytest

from quadkit.ai.llm.structured.parser import (
    build_json_schema,
    extract_json_block,
    validate_against_model,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

try:
    from pydantic import BaseModel

    class _SentimentModel(BaseModel):
        label: Literal["positive", "negative", "neutral"]
        score: float

    _PYDANTIC_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PYDANTIC_AVAILABLE = False
    _SentimentModel = None  # type: ignore[assignment,misc]


@dataclasses.dataclass
class _PersonDC:
    name: str
    age: int


# ---------------------------------------------------------------------------
# extract_json_block
# ---------------------------------------------------------------------------


class TestExtractJsonBlock:
    """Tests for extract_json_block()."""

    def test_raw_json_object(self):
        raw = '{"key": "value", "n": 42}'
        assert extract_json_block(raw) == {"key": "value", "n": 42}

    def test_raw_json_array(self):
        raw = '[1, 2, 3]'
        assert extract_json_block(raw) == [1, 2, 3]

    def test_fenced_json_block(self):
        raw = "```json\n{\"a\": 1}\n```"
        assert extract_json_block(raw) == {"a": 1}

    def test_fenced_json_block_no_language_tag(self):
        raw = "```\n{\"x\": true}\n```"
        assert extract_json_block(raw) == {"x": True}

    def test_json_embedded_in_prose(self):
        raw = "Here is your answer:\n{\"result\": \"ok\"}\nThat's all."
        assert extract_json_block(raw) == {"result": "ok"}

    def test_json_with_leading_prose(self):
        raw = "Sure! Here you go: {\"v\": 99}"
        assert extract_json_block(raw) == {"v": 99}

    def test_invalid_raises_value_error(self):
        with pytest.raises(ValueError, match="No valid JSON found"):
            extract_json_block("This is just plain text, no JSON here.")

    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError):
            extract_json_block("")

    def test_nested_object(self):
        raw = '{"outer": {"inner": [1, 2]}}'
        result = extract_json_block(raw)
        assert result == {"outer": {"inner": [1, 2]}}


# ---------------------------------------------------------------------------
# validate_against_model
# ---------------------------------------------------------------------------


class TestValidateAgainstModel:
    """Tests for validate_against_model()."""

    def test_dict_passthrough(self):
        data = {"a": 1, "b": "hello"}
        result = validate_against_model(data, dict)
        assert result == data

    def test_dict_non_dict_input_raises_type_error(self):
        with pytest.raises(TypeError):
            validate_against_model([1, 2, 3], dict)

    @pytest.mark.skipif(not _PYDANTIC_AVAILABLE, reason="pydantic not installed")
    def test_pydantic_model_valid(self):
        data = {"label": "positive", "score": 0.9}
        instance = validate_against_model(data, _SentimentModel)
        assert instance.label == "positive"
        assert instance.score == pytest.approx(0.9)

    @pytest.mark.skipif(not _PYDANTIC_AVAILABLE, reason="pydantic not installed")
    def test_pydantic_model_validation_failure(self):
        data = {"label": "unknown", "score": "not-a-float"}
        with pytest.raises(ValueError, match="Model validation failed") as exc_info:
            validate_against_model(data, _SentimentModel)

        assert "not-a-float" not in str(exc_info.value)

    def test_dataclass_valid(self):
        data = {"name": "Alice", "age": 30}
        instance = validate_against_model(data, _PersonDC)
        assert instance.name == "Alice"
        assert instance.age == 30

    def test_dataclass_missing_field_raises_value_error(self):
        data = {"name": "Bob"}  # missing age
        with pytest.raises((ValueError, TypeError)):
            validate_against_model(data, _PersonDC)

    def test_plain_class_fallback(self):
        """Plain class accepting **kwargs should work via the fallback branch."""

        class _Simple:
            def __init__(self, x: int, y: str):
                self.x = x
                self.y = y

        data = {"x": 5, "y": "hi"}
        instance = validate_against_model(data, _Simple)
        assert instance.x == 5
        assert instance.y == "hi"


# ---------------------------------------------------------------------------
# build_json_schema
# ---------------------------------------------------------------------------


class TestBuildJsonSchema:
    """Tests for build_json_schema()."""

    @pytest.mark.skipif(not _PYDANTIC_AVAILABLE, reason="pydantic not installed")
    def test_pydantic_model_returns_schema(self):
        schema = build_json_schema(_SentimentModel)
        assert schema.get("type") == "object" or "properties" in schema
        assert "label" in schema.get("properties", schema)

    def test_dataclass_returns_schema(self):
        schema = build_json_schema(_PersonDC)
        assert schema.get("type") == "object"
        props = schema.get("properties", {})
        assert "name" in props
        assert "age" in props

    def test_dataclass_required_fields(self):
        schema = build_json_schema(_PersonDC)
        required = schema.get("required", [])
        assert "name" in required
        assert "age" in required

    def test_dataclass_with_default_not_required(self):
        @dataclasses.dataclass
        class _WithDefault:
            name: str
            optional: str = "default_value"

        schema = build_json_schema(_WithDefault)
        required = schema.get("required", [])
        assert "name" in required
        assert "optional" not in required

    def test_unknown_type_returns_permissive_schema(self):
        class _Arbitrary:
            pass

        schema = build_json_schema(_Arbitrary)
        assert schema == {"type": "object"}
