"""Serialization protocol definitions for Quadkit contracts.

Provides generic serialization protocols used across all extensions
(cache, messaging, tasks, etc.), plus the low-level JSON bytes protocol.

The concrete implementations live in the respective extension packages.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class JsonSerializerProtocol(Protocol):
    """Protocol for JSON serializers."""

    def dumps(self, obj: Any) -> bytes:
        """Serialize object to JSON bytes."""
        ...

    def loads(self, data: bytes | str) -> Any:
        """Deserialize JSON bytes or string to object."""
        ...


@runtime_checkable
class AsyncStringSerializerProtocol(Protocol):
    """Protocol for value serialization.

    Implementations handle conversion between Python objects and string
    representations suitable for storage or transmission.  Used across
    extensions (cache, messaging, tasks, etc.) for consistent serialization.

    Example::

        class JSONSerializer:
            async def serialize(self, value: Any) -> str:
                return json.dumps(value)

            async def deserialize(self, data: str) -> Any:
                return json.loads(data)
    """

    async def serialize(self, value: Any) -> str:
        """Serialize a Python object to string.

        Args:
            value: Python object to serialize.

        Returns:
            String representation.
        """
        ...

    async def deserialize(self, data: str) -> Any:
        """Deserialize string back to Python object.

        Args:
            data: Serialized string data.

        Returns:
            Reconstructed Python object.
        """
        ...


@runtime_checkable
class SerializerProtocol(Protocol):
    """General-purpose serializer/deserializer with typed round-trip support."""

    def serialize(self, obj: Any) -> bytes:
        """Serialize *obj* to raw bytes."""
        ...

    def deserialize(self, data: bytes, type_: type[T]) -> T:
        """Deserialize *data* into an instance of *type_*."""
        ...


__all__ = [
    "AsyncStringSerializerProtocol",
    "JsonSerializerProtocol",
    "SerializerProtocol",
]
