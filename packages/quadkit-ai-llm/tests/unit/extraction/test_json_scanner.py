from __future__ import annotations

import pytest


class TestJsonScanner:
    """Tests for bracket-counting JSON extraction."""

    def test_simple_object(self) -> None:
        from quadkit.ai.llm.extraction._json_scanner import extract_json_objects

        result = extract_json_objects('{"key": "value"}')
        assert result == ['{"key": "value"}']

    def test_nested_object(self) -> None:
        from quadkit.ai.llm.extraction._json_scanner import extract_json_objects

        result = extract_json_objects('{"outer": {"inner": 1}}')
        assert result == ['{"outer": {"inner": 1}}']

    def test_deeply_nested(self) -> None:
        from quadkit.ai.llm.extraction._json_scanner import extract_json_objects

        result = extract_json_objects('{"a": {"b": {"c": 3}}}')
        assert result == ['{"a": {"b": {"c": 3}}}']

    def test_multiple_objects(self) -> None:
        from quadkit.ai.llm.extraction._json_scanner import extract_json_objects

        result = extract_json_objects('{"x": 1} and {"y": 2}')
        assert len(result) == 2
        assert '{"x": 1}' in result
        assert '{"y": 2}' in result

    def test_object_with_array(self) -> None:
        from quadkit.ai.llm.extraction._json_scanner import extract_json_objects

        result = extract_json_objects('{"items": [1, 2, 3]}')
        assert result == ['{"items": [1, 2, 3]}']

    def test_embedded_in_text(self) -> None:
        from quadkit.ai.llm.extraction._json_scanner import extract_json_objects

        result = extract_json_objects('Here is the result: {"name": "Alice", "age": 30} done.')
        assert result == ['{"name": "Alice", "age": 30}']

    def test_empty_text_returns_empty(self) -> None:
        from quadkit.ai.llm.extraction._json_scanner import extract_json_objects

        result = extract_json_objects("")
        assert result == []

    def test_no_json_returns_empty(self) -> None:
        from quadkit.ai.llm.extraction._json_scanner import extract_json_objects

        result = extract_json_objects("no json here")
        assert result == []

    def test_string_with_braces_not_json(self) -> None:
        from quadkit.ai.llm.extraction._json_scanner import extract_json_objects

        # Brace with no matching close — should handle gracefully
        result = extract_json_objects("{incomplete")
        assert result == []

    def test_object_with_string_containing_braces(self) -> None:
        from quadkit.ai.llm.extraction._json_scanner import extract_json_objects

        # Braces inside string values should not confuse the counter
        result = extract_json_objects('{"text": "a { b } c", "x": 1}')
        assert result == ['{"text": "a { b } c", "x": 1}']
