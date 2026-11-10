from __future__ import annotations

import pytest

from quadkit.ai.llm import JSONExtractor, ParseError


class TestJSONExtractor:
    def test_extract_pure_json(self):
        extractor = JSONExtractor()
        text = '{"key": "value", "number": 42}'
        result = extractor.extract(text)
        assert result == {"key": "value", "number": 42}

    def test_extract_from_code_block(self):
        extractor = JSONExtractor()
        text = """Here's the data:
        ```json
        {"name": "Alice", "age": 30}
        ```
        """
        result = extractor.extract(text)
        assert result == {"name": "Alice", "age": 30}

    def test_extract_from_code_block_no_language(self):
        extractor = JSONExtractor()
        text = """```
        {"status": "ok"}
        ```"""
        result = extractor.extract(text)
        assert result == {"status": "ok"}

    def test_extract_from_text(self):
        extractor = JSONExtractor()
        text = 'The answer is {"value": 42} and that is correct.'
        result = extractor.extract(text)
        assert result == {"value": 42}

    def test_extract_multiple(self):
        extractor = JSONExtractor()
        text = """
        First: {"id": 1}
        Second: {"id": 2}
        """
        results = extractor.extract(text, multiple=True)
        assert results == [{"id": 1}, {"id": 2}]

    def test_extract_array(self):
        extractor = JSONExtractor()
        text = '[{"id": 1}, {"id": 2}, {"id": 3}]'
        result = extractor.extract_array(text)
        assert result == [{"id": 1}, {"id": 2}, {"id": 3}]

    def test_extract_array_from_code_block(self):
        extractor = JSONExtractor()
        text = """```json
        [1, 2, 3]
        ```"""
        result = extractor.extract_array(text)
        assert result == [1, 2, 3]

    def test_extract_invalid_json_raises_error(self):
        extractor = JSONExtractor()
        with pytest.raises(ParseError):
            extractor.extract("This is not JSON")

    def test_extract_array_non_array_raises_error(self):
        extractor = JSONExtractor()
        with pytest.raises(ParseError):
            extractor.extract_array('{"not": "an array"}')

    def test_extract_nested_json(self):
        extractor = JSONExtractor()
        text = '{"user": {"name": "Alice", "age": 30}, "active": true}'
        result = extractor.extract(text)
        assert result == {"user": {"name": "Alice", "age": 30}, "active": True}
