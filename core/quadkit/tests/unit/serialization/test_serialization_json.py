"""Tests for JSON serialization module."""

import pytest

from quadkit.serialization.backends import json


class TestJsonDumps:
    """Tests for dumps function."""

    def test_dumps_basic_dict(self) -> None:
        """Test basic dictionary serialization."""
        result = json.dumps({"key": "value"})
        assert b'"key"' in result

    def test_dumps_list(self) -> None:
        """Test list serialization."""
        result = json.dumps([1, 2, 3])
        assert result == b"[1,2,3]"

    def test_dumps_string(self) -> None:
        """Test string serialization."""
        result = json.dumps("hello")
        assert result == b'"hello"'

    def test_dumps_int(self) -> None:
        """Test integer serialization."""
        result = json.dumps(42)
        assert result == b"42"

    def test_dumps_float(self) -> None:
        """Test float serialization."""
        result = json.dumps(3.14)
        assert b"3.14" in result

    def test_dumps_bool(self) -> None:
        """Test boolean serialization."""
        assert json.dumps(True) == b"true"
        assert json.dumps(False) == b"false"

    def test_dumps_none(self) -> None:
        """Test None serialization."""
        assert json.dumps(None) == b"null"

    def test_dumps_nested(self) -> None:
        """Test nested structure serialization."""
        result = json.dumps({"outer": {"inner": [1, 2, 3]}})
        assert b"outer" in result
        assert b"inner" in result

    def test_dumps_sort_keys(self) -> None:
        """Test sort_keys option."""
        result = json.dumps({"b": 1, "a": 2}, sort_keys=True)
        assert result == b'{"a":2,"b":1}'

    def test_dumps_non_str_keys(self) -> None:
        """Test non-string keys."""
        result = json.dumps({1: "one", 2: "two"})
        assert b"1" in result


class TestJsonLoads:
    """Tests for loads function."""

    def test_loads_bytes(self) -> None:
        """Test loading from bytes."""
        result = json.loads(b'{"key": "value"}')
        assert result == {"key": "value"}

    def test_loads_string(self) -> None:
        """Test loading from string."""
        result = json.loads('{"key": "value"}')
        assert result == {"key": "value"}

    def test_loads_list(self) -> None:
        """Test loading list."""
        result = json.loads(b"[1, 2, 3]")
        assert result == [1, 2, 3]

    def test_loads_nested(self) -> None:
        """Test loading nested structure."""
        result = json.loads(b'{"outer": {"inner": [1, 2, 3]}}')
        assert result == {"outer": {"inner": [1, 2, 3]}}

    def test_loads_unicode(self) -> None:
        """Test loading unicode."""
        result = json.loads(b'{"emoji": "\\ud83d\\ude00"}')
        assert "emoji" in result


class TestJsonDumpsStr:
    """Tests for dumps_str function."""

    def test_dumps_str_returns_string(self) -> None:
        """Test dumps_str returns string."""
        result = json.dumps_str({"key": "value"})
        assert isinstance(result, str)
        assert '"key"' in result


class TestJsonLoadsStr:
    """Tests for loads_str function."""

    def test_loads_str_from_string(self) -> None:
        """Test loads_str from string."""
        result = json.loads_str('{"key": "value"}')
        assert result == {"key": "value"}


class TestJsonBackend:
    """Tests for JSON_BACKEND constant."""

    def test_json_backend_defined(self) -> None:
        """Test JSON_BACKEND is defined."""
        assert json.JSON_BACKEND in ("orjson", "stdlib")


class TestJsonDecodeError:
    """Tests for JSONDecodeError."""

    def test_json_decode_error_import(self) -> None:
        """Test JSONDecodeError is available."""
        assert json.JSONDecodeError is not None


class TestOrjsonSerializer:
    """Tests for OrjsonSerializer class."""

    def test_init_default(self) -> None:
        """Test initialization with defaults."""
        serializer = json.OrjsonSerializer()
        assert serializer is not None

    def test_init_with_config(self) -> None:
        """Test initialization with config."""
        from quadkit.serialization.config import SerializationConfig

        config = SerializationConfig()
        serializer = json.OrjsonSerializer(config)
        assert serializer is not None

    def test_dumps_returns_bytes(self) -> None:
        """Test dumps returns bytes."""
        serializer = json.OrjsonSerializer()
        result = serializer.dumps({"key": "value"})
        assert isinstance(result, bytes)

    def test_loads_bytes(self) -> None:
        """Test loads from bytes."""
        serializer = json.OrjsonSerializer()
        result = serializer.loads(b'{"key": "value"}')
        assert result == {"key": "value"}

    def test_loads_string(self) -> None:
        """Test loads from string."""
        serializer = json.OrjsonSerializer()
        result = serializer.loads('{"key": "value"}')
        assert result == {"key": "value"}

    def test_serialize_method(self) -> None:
        """Test serialize method."""
        serializer = json.OrjsonSerializer()
        result = serializer.serialize({"key": "value"})
        assert isinstance(result, bytes)

    def test_deserialize_method(self) -> None:
        """Test deserialize method."""
        serializer = json.OrjsonSerializer()
        result = serializer.deserialize(b'{"key": "value"}', dict)
        assert result == {"key": "value"}


class TestStdlibSerializer:
    """Tests for StdlibSerializer class."""

    def test_init_default(self) -> None:
        """Test initialization with defaults."""
        serializer = json.StdlibSerializer()
        assert serializer is not None

    def test_init_with_config(self) -> None:
        """Test initialization with config."""
        from quadkit.serialization.config import SerializationConfig

        config = SerializationConfig()
        serializer = json.StdlibSerializer(config)
        assert serializer is not None

    def test_dumps_returns_bytes(self) -> None:
        """Test dumps returns bytes."""
        serializer = json.StdlibSerializer()
        result = serializer.dumps({"key": "value"})
        assert isinstance(result, bytes)

    def test_loads_bytes(self) -> None:
        """Test loads from bytes."""
        serializer = json.StdlibSerializer()
        result = serializer.loads(b'{"key": "value"}')
        assert result == {"key": "value"}

    def test_loads_string(self) -> None:
        """Test loads from string."""
        serializer = json.StdlibSerializer()
        result = serializer.loads('{"key": "value"}')
        assert result == {"key": "value"}

    def test_serialize_method(self) -> None:
        """Test serialize method."""
        serializer = json.StdlibSerializer()
        result = serializer.serialize({"key": "value"})
        assert isinstance(result, bytes)

    def test_deserialize_method(self) -> None:
        """Test deserialize method."""
        serializer = json.StdlibSerializer()
        result = serializer.deserialize(b'{"key": "value"}', dict)
        assert result == {"key": "value"}

    def test_dumps_with_indent(self) -> None:
        """Test dumps with indent config."""
        from quadkit.serialization.config import SerializationConfig

        config = SerializationConfig(indent=2)
        serializer = json.StdlibSerializer(config)
        result = serializer.dumps({"key": "value"})
        assert b"\n" in result

    def test_dumps_with_ensure_ascii(self) -> None:
        """Test dumps with ensure_ascii config."""
        from quadkit.serialization.config import SerializationConfig

        config = SerializationConfig(ensure_ascii=True)
        serializer = json.StdlibSerializer(config)
        result = serializer.dumps({"key": "value"})
        assert isinstance(result, bytes)


class TestJsonModuleExports:
    """Tests for module exports."""

    def test_all_contains_expected(self) -> None:
        """Test __all__ contains expected items."""
        expected = [
            "JSON_BACKEND",
            "JSONDecodeError",
            "OrjsonSerializer",
            "StdlibSerializer",
            "dumps",
            "dumps_str",
            "loads",
            "loads_str",
        ]
        for item in expected:
            assert item in json.__all__


class TestDumpsStrAndLoadsStr:
    """Additional tests for dumps_str and loads_str."""

    def test_dumps_str_nested(self) -> None:
        """Test dumps_str with nested structure."""
        result = json.dumps_str({"outer": {"inner": [1, 2]}})
        assert '"outer"' in result

    def test_dumps_str_empty(self) -> None:
        """Test dumps_str with empty object."""
        result = json.dumps_str({})
        assert result == "{}"

    def test_dumps_str_list(self) -> None:
        """Test dumps_str with list."""
        result = json.dumps_str([1, 2, 3])
        assert result == "[1,2,3]"

    def test_dumps_str_unicode_content(self) -> None:
        """Test dumps_str with unicode content."""
        result = json.dumps_str({"text": "héllo"})
        assert "héllo" in result

    def test_loads_str_empty(self) -> None:
        """Test loads_str with empty object."""
        result = json.loads_str("{}")
        assert result == {}

    def test_loads_str_list(self) -> None:
        """Test loads_str with list."""
        result = json.loads_str("[1,2,3]")
        assert result == [1, 2, 3]

    def test_loads_str_unicode(self) -> None:
        """Test loads_str with unicode."""
        result = json.loads_str('{"text": "héllo"}')
        assert result == {"text": "héllo"}

    def test_roundtrip_dict(self) -> None:
        """Test roundtrip serialize/deserialize."""
        original = {"key": "value", "num": 42}
        serialized = json.dumps_str(original)
        deserialized = json.loads_str(serialized)
        assert deserialized == original

    def test_roundtrip_list(self) -> None:
        """Test roundtrip with list."""
        original = [1, 2, {"a": "b"}]
        serialized = json.dumps_str(original)
        deserialized = json.loads_str(serialized)
        assert deserialized == original
