"""JSON serialization utilities with orjson support.

Provides a standard JSON serialization interface across all Quadkit packages
with automatic fallback to stdlib json when orjson is not available.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

# Try to use orjson for JSON operations, but fall back to the standard library if it's not
try:
    import orjson  # noqa: TID251

    def _default_encoder(obj: Any) -> Any:
        """Default encoder for types orjson doesn't handle."""
        from quadkit.serialization.domain import json_serialize

        return json_serialize(obj)

    def dumps(obj: Any, **kwargs: Any) -> bytes:
        """Serialize object to JSON bytes using orjson.

        Args:
            obj: Object to serialize
            **kwargs: Additional options (supports sort_keys)

        Returns:
            JSON bytes

        Note:
            Uses orjson.dumps with sensible defaults:
            - Non-string keys allowed
            - NumPy array serialization enabled
        """
        option = orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY
        if kwargs.get("sort_keys"):
            option |= orjson.OPT_SORT_KEYS

        return orjson.dumps(obj, default=_default_encoder, option=option)

    def loads(data: bytes | str, **_kwargs: Any) -> Any:
        """Deserialize JSON bytes or string to object using orjson.

        Args:
            data: JSON bytes or string to deserialize
            **_kwargs: Additional options (ignored, for compatibility)

        Returns:
            Deserialized object
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        return orjson.loads(data)

    JSON_BACKEND = "orjson"

except ImportError:
    # Fallback to standard library for packages that don't have orjson
    import json as _stdlib_json  # noqa: TID251

    def dumps(obj: Any, **kwargs: Any) -> bytes:
        """Serialize object to JSON bytes using stdlib json.

        Args:
            obj: Object to serialize
            **kwargs: Additional options passed to json.dumps

        Returns:
            JSON bytes
        """

        def default_encoder(obj: Any) -> Any:
            from quadkit.serialization.domain import json_serialize

            return json_serialize(obj)

        # Set sensible defaults
        kwargs.setdefault("default", default_encoder)
        kwargs.setdefault("ensure_ascii", False)
        # Produce compact JSON like orjson (no spaces after separators) to
        # keep outputs consistent between backends and tests.
        kwargs.setdefault("separators", (",", ":"))

        return _stdlib_json.dumps(obj, **kwargs).encode("utf-8")

    def loads(data: bytes | str, **kwargs: Any) -> Any:
        """Deserialize JSON bytes or string to object using stdlib json.

        Args:
            data: JSON bytes or string to deserialize
            **kwargs: Additional options passed to json.loads

        Returns:
            Deserialized object
        """
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return _stdlib_json.loads(data, **kwargs)

    JSON_BACKEND = "stdlib"


def dumps_str(obj: Any, **kwargs: Any) -> str:
    """Serialize object to JSON string.

    Args:
        obj: Object to serialize
        **kwargs: Additional options

    Returns:
        JSON string
    """
    return dumps(obj, **kwargs).decode("utf-8")


def loads_str(data: str, **kwargs: Any) -> Any:
    """Deserialize JSON string to object.

    Args:
        data: JSON string to deserialize
        **kwargs: Additional options

    Returns:
        Deserialized object
    """
    return loads(data.encode("utf-8"), **kwargs)


# Standard library JSONDecodeError
from json import JSONDecodeError  # noqa: TID251

# ---------------------------------------------------------------------------
# OOP JSON serializer classes (previously in json_serializer.py)
# ---------------------------------------------------------------------------

if TYPE_CHECKING:
    from quadkit.serialization.config import SerializationConfig


class OrjsonSerializer:
    """High-performance JSON serializer using orjson."""

    def __init__(self, config: SerializationConfig | None = None) -> None:
        """Initialize with optional config."""
        from quadkit.serialization.config import SerializationConfig
        from quadkit.serialization.types import JSONBackend

        self._config = config or SerializationConfig(
            preferred_backend=JSONBackend.ORJSON
        )

    def dumps(self, obj: Any) -> bytes:
        """Serialize object to JSON bytes using orjson."""
        import orjson  # noqa: TID251

        option = orjson.OPT_NON_STR_KEYS | orjson.OPT_SERIALIZE_NUMPY
        return orjson.dumps(obj, default=self._default_handler, option=option)

    def loads(self, data: bytes | str) -> Any:
        """Deserialize JSON bytes or string to object using orjson."""
        import orjson  # noqa: TID251

        if isinstance(data, str):
            data = data.encode(self._config.encoding)
        return orjson.loads(data)

    def serialize(self, obj: Any) -> bytes:
        """Satisfy SerializerProtocol."""
        return self.dumps(obj)

    def deserialize(self, data: bytes, type_: type[Any]) -> Any:
        """Satisfy SerializerProtocol."""
        return self.loads(data)

    @staticmethod
    def _default_handler(obj: Any) -> Any:
        """Default handler for types orjson doesn't handle natively."""
        from quadkit.serialization.domain import json_serialize

        return json_serialize(obj)


class StdlibSerializer:
    """Fallback JSON serializer using stdlib json."""

    def __init__(self, config: SerializationConfig | None = None) -> None:
        """Initialize with optional config."""
        from quadkit.serialization.config import SerializationConfig
        from quadkit.serialization.types import JSONBackend

        self._config = config or SerializationConfig(
            preferred_backend=JSONBackend.STDLIB
        )

    def dumps(self, obj: Any) -> bytes:
        """Serialize object to JSON bytes using stdlib json."""
        import json as _json  # noqa: TID251

        def default_handler(o: Any) -> Any:
            from quadkit.serialization.domain import json_serialize

            return json_serialize(o)

        return _json.dumps(
            obj,
            default=default_handler,
            ensure_ascii=self._config.ensure_ascii,
            indent=self._config.indent,
            separators=(",", ":") if self._config.indent is None else None,
        ).encode(self._config.encoding)

    def loads(self, data: bytes | str) -> Any:
        """Deserialize JSON bytes or string to object using stdlib json."""
        import json as _json  # noqa: TID251

        if isinstance(data, bytes):
            data = data.decode(self._config.encoding)
        return _json.loads(data)

    def serialize(self, obj: Any) -> bytes:
        """Satisfy SerializerProtocol."""
        return self.dumps(obj)

    def deserialize(self, data: bytes, type_: type[Any]) -> Any:
        """Satisfy SerializerProtocol."""
        return self.loads(data)


__all__ = [
    "JSON_BACKEND",
    "JSONDecodeError",
    "OrjsonSerializer",
    "StdlibSerializer",
    "dumps",
    "dumps_str",
    "loads",
    "loads_str",
]
