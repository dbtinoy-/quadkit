"""AsyncStringSerializerProtocol registry for data serialization.

This module provides a registry pattern for data serializers (JSON, YAML, MessagePack, etc).
"""

from __future__ import annotations

import abc
import base64
from datetime import date, datetime
from decimal import Decimal
from typing import Any, ClassVar

from quadkit import serialization as json


class AsyncStringSerializerProtocol(abc.ABC):
    """Abstract base class for serializers."""

    name: ClassVar[str]
    content_type: ClassVar[str]
    file_extension: ClassVar[str]

    @abc.abstractmethod
    def serialize(self, data: Any) -> str | bytes:
        """Serialize data to string or bytes."""

    @abc.abstractmethod
    def deserialize(self, data: str | bytes) -> Any:
        """Deserialize data from string or bytes."""


class JSONSerializer(AsyncStringSerializerProtocol):
    """JSON serializer."""

    name = "json"
    content_type = "application/json"
    file_extension = "json"

    def serialize(self, data: Any) -> str:
        return json.dumps(data, indent=2, default=self._json_serial).decode("utf-8")

    def deserialize(self, data: str | bytes) -> Any:
        return json.loads(data)

    @staticmethod
    def _json_serial(obj: Any) -> Any:
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode()
        raise TypeError(f"Type {type(obj)} not serializable")


class CompactJSONSerializer(AsyncStringSerializerProtocol):
    """Compact JSON serializer (no indentation)."""

    name = "json-minified"
    content_type = "application/json"
    file_extension = "json"

    def serialize(self, data: Any) -> str:
        return json.dumps(
            data,
            separators=(",", ":"),
            default=JSONSerializer._json_serial,
        ).decode("utf-8")

    def deserialize(self, data: str | bytes) -> Any:
        return json.loads(data)


class YAMLSerializer(AsyncStringSerializerProtocol):
    """YAML serializer."""

    name = "yaml"
    content_type = "application/x-yaml"
    file_extension = "yaml"

    def serialize(self, data: Any) -> str:
        try:
            import yaml

            return yaml.dump(data, default_flow_style=False, sort_keys=False)
        except ImportError:
            return json.dumps(data, indent=2).decode("utf-8")

    def deserialize(self, data: str | bytes) -> Any:
        try:
            import yaml
            from yaml import SafeLoader
        except ImportError:
            raise ImportError("PyYAML not installed") from None

        return yaml.load(data, Loader=SafeLoader)


class MessagePackSerializer(AsyncStringSerializerProtocol):
    """MessagePack serializer."""

    name = "msgpack"
    content_type = "application/msgpack"
    file_extension = "msgpack"

    def serialize(self, data: Any) -> bytes:
        try:
            import msgpack
        except ImportError:
            raise ImportError("msgpack not installed") from None

        packed: bytes = msgpack.packb(data, use_bin_type=True)
        return packed

    def deserialize(self, data: str | bytes) -> Any:
        try:
            import msgpack
        except ImportError:
            raise ImportError("msgpack not installed") from None

        if isinstance(data, str):
            data = data.encode("utf-8")
        unpacked: Any = msgpack.unpackb(data, raw=False)
        return unpacked


class CBORSerializer(AsyncStringSerializerProtocol):
    """CBOR serializer."""

    name = "cbor"
    content_type = "application/cbor"
    file_extension = "cbor"

    def serialize(self, data: Any) -> bytes:
        try:
            import cbor2  # type: ignore[import-not-found]
        except ImportError:
            raise ImportError("cbor2 not installed") from None

        dumped: bytes = cbor2.dumps(data)
        return dumped

    def deserialize(self, data: str | bytes) -> Any:
        try:
            import cbor2
        except ImportError:
            raise ImportError("cbor2 not installed") from None

        if isinstance(data, str):
            data = data.encode("utf-8")
        loaded: Any = cbor2.loads(data)
        return loaded


class TOMLSerializer(AsyncStringSerializerProtocol):
    """TOML serializer."""

    name = "toml"
    content_type = "application/toml"
    file_extension = "toml"

    def serialize(self, data: Any) -> str:
        try:
            import tomli  # noqa: F401
            import tomli_w
        except ImportError:
            raise ImportError("tomli not installed") from None

        import io

        output = io.BytesIO()
        tomli_w.dump(data, output)
        return output.getvalue().decode("utf-8")

    def deserialize(self, data: str | bytes) -> Any:
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[no-redef]
            except ImportError:
                raise ImportError("tomli not installed") from None

        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return tomllib.loads(data)


class SerializerRegistry:
    """Registry for serializers.

    Provides a pluggable way to add new serializers.
    """

    def __init__(self) -> None:
        self._serializers: dict[str, AsyncStringSerializerProtocol] = {}

    def register(self, serializer: type[AsyncStringSerializerProtocol]) -> None:
        """Register a serializer class."""
        instance = serializer()
        self._serializers[serializer.name] = instance

    def get(self, name: str) -> AsyncStringSerializerProtocol | None:
        """Get a serializer by name."""
        return self._serializers.get(name)

    def get_all(self) -> dict[str, AsyncStringSerializerProtocol]:
        """Get all registered serializers."""
        return self._serializers.copy()

    def get_choices(self) -> list[str]:
        """Get list of available serializer names."""
        return list(self._serializers.keys())

    @classmethod
    def _default_entries(cls) -> tuple[type[AsyncStringSerializerProtocol], ...]:
        """The complete in-package built-in set, declared exactly once."""
        return (
            JSONSerializer,
            CompactJSONSerializer,
            YAMLSerializer,
            MessagePackSerializer,
            CBORSerializer,
            TOMLSerializer,
        )

    @classmethod
    def with_defaults(cls) -> SerializerRegistry:
        """Return an instance populated with the built-in serializers."""
        registry = cls()
        for entry in cls._default_entries():
            registry.register(entry)
        return registry


def serialize(data: Any, file_format: str = "json") -> str | bytes:
    """Serialize data using the specified format."""
    serializer = SerializerRegistry.with_defaults().get(file_format)
    if not serializer:
        raise ValueError(f"Unknown format: {file_format}")
    return serializer.serialize(data)


def deserialize(data: str | bytes, file_format: str = "json") -> Any:
    """Deserialize data using the specified format."""
    serializer = SerializerRegistry.with_defaults().get(file_format)
    if not serializer:
        raise ValueError(f"Unknown format: {file_format}")
    return serializer.deserialize(data)


__all__ = [
    "AsyncStringSerializerProtocol",
    "CBORSerializer",
    "CompactJSONSerializer",
    "JSONSerializer",
    "MessagePackSerializer",
    "SerializerRegistry",
    "TOMLSerializer",
    "YAMLSerializer",
    "deserialize",
    "serialize",
]
