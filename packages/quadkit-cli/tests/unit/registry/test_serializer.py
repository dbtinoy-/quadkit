from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from quadkit.cli.registry.serializer import (
    AsyncStringSerializerProtocol,
    CBORSerializer,
    CompactJSONSerializer,
    JSONSerializer,
    MessagePackSerializer,
    SerializerRegistry,
    TOMLSerializer,
    YAMLSerializer,
    deserialize,
    serialize,
)


class TestJSONSerializer:
    def test_serialize_deserialize_roundtrip(self) -> None:
        s = JSONSerializer()
        data = {"name": "test", "count": 42}
        serialized = s.serialize(data)
        deserialized = s.deserialize(serialized)
        assert deserialized == data

    def test_serialize_datetime(self) -> None:
        s = JSONSerializer()
        data = {"when": datetime(2024, 1, 1, 12, 0, 0)}
        serialized = s.serialize(data)
        assert "2024-01-01T12:00:00" in serialized

    def test_serialize_date(self) -> None:
        s = JSONSerializer()
        data = {"when": date(2024, 1, 1)}
        serialized = s.serialize(data)
        assert "2024-01-01" in serialized

    def test_serialize_decimal(self) -> None:
        s = JSONSerializer()
        data = {"price": Decimal("12.50")}
        serialized = s.serialize(data)
        assert "12.5" in serialized

    def test_serialize_bytes(self) -> None:
        s = JSONSerializer()
        data = {"data": b"hello"}
        serialized = s.serialize(data)
        assert "hello" in serialized

    def test_serialize_unsupported_type(self) -> None:
        s = JSONSerializer()
        result = s.serialize({"obj": object()})
        assert "<object object at" in result


class TestCompactJSONSerializer:
    def test_no_indentation(self) -> None:
        s = CompactJSONSerializer()
        result = s.serialize({"a": 1, "b": 2})
        assert "\n" not in result

    def test_roundtrip(self) -> None:
        s = CompactJSONSerializer()
        data = {"x": 1, "y": "test"}
        serialized = s.serialize(data)
        assert s.deserialize(serialized) == data


class TestYAMLSerializer:
    def test_serialize(self) -> None:
        s = YAMLSerializer()
        data = {"name": "test", "value": 42}
        result = s.serialize(data)
        assert "name:" in result
        assert "test" in result

    def test_serialize_fallback(self) -> None:
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            s = YAMLSerializer()
            result = s.serialize({"a": 1})
            assert "a" in result

    def test_deserialize(self) -> None:
        s = YAMLSerializer()
        yaml_str = "name: test\nvalue: 42\n"
        result = s.deserialize(yaml_str)
        assert result == {"name": "test", "value": 42}

    def test_deserialize_no_yaml(self) -> None:
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            s = YAMLSerializer()
            with pytest.raises(ImportError):
                s.deserialize("key: val")


class TestMessagePackSerializer:
    def test_roundtrip(self) -> None:
        mock_msgpack = MagicMock()
        mock_msgpack.packb.return_value = b"\x01"
        mock_msgpack.unpackb.return_value = {"a": 1, "b": "hello", "c": [1, 2, 3]}
        with patch.dict("sys.modules", {"msgpack": mock_msgpack}):
            s = MessagePackSerializer()
            data = {"a": 1, "b": "hello", "c": [1, 2, 3]}
            serialized = s.serialize(data)
            assert s.deserialize(serialized) == data

    def test_serialize_no_msgpack(self) -> None:
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "msgpack":
                raise ImportError
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            s = MessagePackSerializer()
            with pytest.raises(ImportError):
                s.serialize({"a": 1})


class TestCBORSerializer:
    def test_roundtrip(self) -> None:
        mock_cbor2 = MagicMock()
        mock_cbor2.dumps.return_value = b"\x01"
        mock_cbor2.loads.return_value = {"a": 1, "b": "test"}
        with patch.dict("sys.modules", {"cbor2": mock_cbor2}):
            s = CBORSerializer()
            data = {"a": 1, "b": "test"}
            serialized = s.serialize(data)
            assert s.deserialize(serialized) == data

    def test_serialize_no_cbor2(self) -> None:
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "cbor2":
                raise ImportError
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            s = CBORSerializer()
            with pytest.raises(ImportError):
                s.serialize({"a": 1})


class TestTOMLSerializer:
    def test_serialize(self) -> None:
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "tomli":
                raise ImportError
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            s = TOMLSerializer()
            with pytest.raises(ImportError):
                s.serialize({"a": 1})

    def test_deserialize_no_tomllib(self) -> None:
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name in ("tomllib", "tomli"):
                raise ImportError
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            s = TOMLSerializer()
            with pytest.raises(ImportError):
                s.deserialize("key = 1")


class TestSerializerRegistry:
    def test_get_default_serializers(self) -> None:
        reg = SerializerRegistry.with_defaults()
        json_s = reg.get("json")
        assert json_s is not None
        assert json_s.name == "json"

    def test_get_nonexistent(self) -> None:
        reg = SerializerRegistry.with_defaults()
        assert reg.get("nonexistent") is None

    def test_get_all(self) -> None:
        reg = SerializerRegistry.with_defaults()
        all_s = reg.get_all()
        assert "json" in all_s
        assert "yaml" in all_s

    def test_get_choices(self) -> None:
        reg = SerializerRegistry.with_defaults()
        choices = reg.get_choices()
        assert "json" in choices
        assert "yaml" in choices

    def test_custom_registration(self) -> None:
        reg = SerializerRegistry.with_defaults()

        class FakeSerializer(AsyncStringSerializerProtocol):
            name = "fake"
            content_type = "text/plain"
            file_extension = "txt"

            def serialize(self, data):
                return str(data)

            def deserialize(self, data):
                return str(data)

        reg.register(FakeSerializer)
        assert reg.get("fake") is not None


class TestSerializeFunctions:
    def test_serialize_json(self) -> None:
        result = serialize({"a": 1}, "json")
        assert isinstance(result, str)
        assert "a" in result

    def test_serialize_unknown(self) -> None:
        with pytest.raises(ValueError):
            serialize({"a": 1}, "unknown_format")

    def test_deserialize_json(self) -> None:
        result = deserialize('{"a": 1}', "json")
        assert result == {"a": 1}

    def test_deserialize_unknown(self) -> None:
        with pytest.raises(ValueError):
            deserialize("data", "unknown_format")
