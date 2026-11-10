"""Tests for the bracket-counting JSON extractor on StructuredOutputExtractor."""

from __future__ import annotations

import pytest

from quadkit.ai.llm.structured.extractor import StructuredOutputExtractor


class TestBracketCountingExtraction:
    """Tests for the bracket-counting JSON extractor."""

    @pytest.fixture
    def extractor(self) -> StructuredOutputExtractor:
        return StructuredOutputExtractor()

    def test_simple_json_object_extracted(self, extractor: StructuredOutputExtractor) -> None:
        text = 'Sure, here is the answer: {"name": "Alice", "age": 30}'
        result = extractor._extract_json_block(text)
        assert result == '{"name": "Alice", "age": 30}'

    def test_nested_json_object_extracted(self, extractor: StructuredOutputExtractor) -> None:
        text = 'Result: {"user": {"name": "Bob", "scores": [1, 2, 3]}, "status": "ok"}'
        result = extractor._extract_json_block(text)
        assert result == '{"user": {"name": "Bob", "scores": [1, 2, 3]}, "status": "ok"}'

    def test_multiple_json_objects_returns_first(self, extractor: StructuredOutputExtractor) -> None:
        # Regex-based extraction fails here — bracket counting picks the FIRST complete object
        text = 'First: {"a": 1} then {"b": 2}'
        result = extractor._extract_json_block(text)
        assert result == '{"a": 1}'

    def test_json_with_braces_in_string_values(self, extractor: StructuredOutputExtractor) -> None:
        # This is the catastrophic failure case for the old regex
        text = 'Note: {some text} then the JSON: {"key": "value with {braces}"}'
        result = extractor._extract_json_block(text)
        assert result == '{"key": "value with {braces}"}'

    def test_no_json_returns_none(self, extractor: StructuredOutputExtractor) -> None:
        text = "There is no JSON object here at all."
        result = extractor._extract_json_block(text)
        assert result is None

    def test_empty_object_extracted(self, extractor: StructuredOutputExtractor) -> None:
        text = "The result is {}"
        result = extractor._extract_json_block(text)
        assert result == "{}"

    def test_json_array_extracted(self, extractor: StructuredOutputExtractor) -> None:
        text = 'Results: [{"id": 1}, {"id": 2}]'
        result = extractor._extract_json_block(text)
        assert result == '[{"id": 1}, {"id": 2}]'

    def test_markdown_code_fence_json_extracted(self, extractor: StructuredOutputExtractor) -> None:
        text = '```json\n{"status": "ok", "count": 5}\n```'
        result = extractor._extract_json_block(text)
        assert result == '{"status": "ok", "count": 5}'
