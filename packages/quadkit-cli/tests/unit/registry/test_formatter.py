from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quadkit.cli.registry.formatter import (
    FormatOptions,
    FormatterRegistry,
    JSONFormatter,
    OutputFormatter,
    SimpleFormatter,
    TableFormatter,
    YAMLFormatter,
    format_output,
)


class TestJSONFormatter:
    def test_format(self) -> None:
        f = JSONFormatter()
        result = f.format({"a": 1, "b": "test"})
        assert '"a"' in result
        assert '"b"' in result

    def test_format_with_options(self) -> None:
        f = JSONFormatter()
        with patch("quadkit.cli.registry.formatter.json") as mock_json:
            mock_json.dumps.return_value = b'{"a": 1}'
            result = f.format({"a": 1}, FormatOptions(indent=4, sort_keys=True))
            mock_json.dumps.assert_called_once_with(
                {"a": 1}, indent=4, sort_keys=True, default=str
            )
        assert result == '{"a": 1}'

    def test_parse(self) -> None:
        f = JSONFormatter()
        result = f.parse('{"a": 1}')
        assert result == {"a": 1}

    def test_name_and_extension(self) -> None:
        f = JSONFormatter()
        assert f.name == "json"
        assert f.file_extension == "json"
        assert f.content_type == "application/json"


class TestYAMLFormatter:
    def test_format(self) -> None:
        f = YAMLFormatter()
        result = f.format({"name": "test"})
        assert "name:" in result

    def test_format_fallback(self) -> None:
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            f = YAMLFormatter()
            result = f.format({"a": 1})
            assert "a" in result

    def test_parse(self) -> None:
        f = YAMLFormatter()
        result = f.parse("name: test\n")
        assert result == {"name": "test"}

    def test_parse_fallback_error(self) -> None:
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            f = YAMLFormatter()
            with pytest.raises(ValueError):
                f.parse("name: test")


class TestTableFormatter:
    def test_format_empty(self) -> None:
        f = TableFormatter()
        result = f.format([])
        assert result == "[]"

    def test_format_dict_list(self) -> None:
        f = TableFormatter()
        data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        result = f.format(data)
        assert "name" in result
        assert "Alice" in result

    def test_format_list_of_lists(self) -> None:
        f = TableFormatter()
        data = [["a", 1], ["b", 2]]
        result = f.format(data)
        assert "a" in result
        assert "b" in result

    def test_format_non_list(self) -> None:
        f = TableFormatter()
        assert f.format("just a string") == "just a string"

    def test_parse_raises(self) -> None:
        f = TableFormatter()
        with pytest.raises(NotImplementedError):
            f.parse("")


class TestSimpleFormatter:
    def test_format_dict(self) -> None:
        f = SimpleFormatter()
        result = f.format({"key": "value"})
        assert "key: value" in result

    def test_format_list(self) -> None:
        f = SimpleFormatter()
        result = f.format(["a", "b"])
        assert result == "a\nb"

    def test_format_string(self) -> None:
        f = SimpleFormatter()
        assert f.format("hello") == "hello"

    def test_parse(self) -> None:
        f = SimpleFormatter()
        result = f.parse("key: value\nfoo: bar")
        assert result == {"key": "value", "foo": "bar"}


class TestFormatterRegistry:
    def test_get_default_formatters(self) -> None:
        reg = FormatterRegistry.with_defaults()
        assert reg.get("json") is not None
        assert reg.get("yaml") is not None
        assert reg.get("table") is not None

    def test_get_nonexistent(self) -> None:
        reg = FormatterRegistry.with_defaults()
        assert reg.get("nonexistent") is None

    def test_get_all(self) -> None:
        reg = FormatterRegistry.with_defaults()
        all_f = reg.get_all()
        assert "json" in all_f

    def test_get_choices(self) -> None:
        reg = FormatterRegistry.with_defaults()
        choices = reg.get_choices()
        assert "json" in choices

    def test_custom_registration(self) -> None:
        reg = FormatterRegistry.with_defaults()

        class FakeFormatter(OutputFormatter):
            name = "fake"
            content_type = "text/plain"
            file_extension = "txt"

            def format(self, data, options=None):
                return str(data)

            def parse(self, input_str):
                return input_str

        reg.register(FakeFormatter)
        assert reg.get("fake") is not None


class TestFormatOutput:
    def test_json(self) -> None:
        result = format_output({"a": 1}, "json")
        assert "a" in result

    def test_unknown_format(self) -> None:
        with pytest.raises(ValueError):
            format_output({}, "unknown")
