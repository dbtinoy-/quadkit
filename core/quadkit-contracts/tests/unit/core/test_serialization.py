"""Tests for serialization protocols."""

from __future__ import annotations

from quadkit.contracts.core.serialization import (
    JsonSerializerProtocol,
    AsyncStringSerializerProtocol,
    SerializerProtocol,
)


class TestJsonSerializerProtocol:
    """Tests for JsonSerializerProtocol."""

    def test_has_dumps_method(self) -> None:
        assert hasattr(JsonSerializerProtocol, "dumps")

    def test_has_loads_method(self) -> None:
        assert hasattr(JsonSerializerProtocol, "loads")


class TestAsyncStringSerializerProtocol:
    """Tests for AsyncStringSerializerProtocol."""

    def test_has_serialize_method(self) -> None:
        assert hasattr(AsyncStringSerializerProtocol, "serialize")

    def test_has_deserialize_method(self) -> None:
        assert hasattr(AsyncStringSerializerProtocol, "deserialize")


class TestSerializerProtocol:
    """Tests for SerializerProtocol."""

    def test_has_serialize_method(self) -> None:
        assert hasattr(SerializerProtocol, "serialize")

    def test_has_deserialize_method(self) -> None:
        assert hasattr(SerializerProtocol, "deserialize")