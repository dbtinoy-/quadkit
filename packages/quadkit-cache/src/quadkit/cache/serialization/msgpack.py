"""MessagePack serializer for Quadkit Cache.

Provides compact binary serialization via the ``msgpack`` library.
Approximately 2-5x more compact than JSON for numeric-heavy payloads,
and avoids the overhead of JSON string encoding.

``msgpack`` is an optional dependency — the module is importable even
without it, but instantiation will raise ``ImportError`` if the package
is not installed.  Add ``msgpack`` to your project dependencies to enable:

    uv add msgpack

"""

from __future__ import annotations

import asyncio
from typing import Any

from quadkit.cache.exceptions import CacheSerializationError


class MsgPackSerializer:
    """Binary MessagePack serializer for cache backends.

    Uses the ``msgpack`` third-party library for compact, language-neutral
    binary serialization.  Stores values as ``bytes`` (not ``str``), so
    the cache backend must support binary values (Redis, Memcached do).

    Compared with :class:`~quadkit.cache.serialization.json.JSONSerializer`:
    - More compact for numeric/binary-heavy payloads.
    - Faster encode/decode for large nested structures.
    - **Not** human-readable.
    - Requires ``msgpack`` installed (``uv add msgpack``).

    Implements the ``AsyncStringSerializerProtocol`` interface but stores
    Base64-encoded bytes as a str so it is wire-compatible with string-only
    backends.

    Raises:
        ImportError: If ``msgpack`` is not installed.
    """

    def __init__(self, *, use_bin_type: bool = True, raw: bool = False) -> None:
        """Initialise the serializer, verifying msgpack is importable.

        Args:
            use_bin_type: Pass Python ``bytes`` objects as msgpack ``bin``
                type (recommended — required for Python 3).
            raw: If ``True``, unpack msgpack ``str`` as Python ``bytes``
                (legacy mode).  Should be ``False`` for modern use.

        Raises:
            ImportError: If the ``msgpack`` package is not installed.
        """
        try:
            import msgpack  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "MsgPackSerializer requires the 'msgpack' package. "
                "Install it with: uv add msgpack"
            ) from exc

        self._use_bin_type = use_bin_type
        self._raw = raw

    async def serialize(self, value: Any) -> str:
        """Serialize *value* to a Base64-encoded MessagePack string.

        Args:
            value: Any msgpack-serializable Python value.

        Returns:
            Base64-encoded string representation of the packed bytes.

        Raises:
            CacheSerializationError: If serialization fails.
        """
        import base64

        import msgpack

        try:
            packed: bytes = await asyncio.to_thread(
                msgpack.packb,
                value,
                use_bin_type=self._use_bin_type,
            )
            return base64.b64encode(packed).decode("ascii")
        except (TypeError, ValueError, msgpack.PackException) as exc:
            raise CacheSerializationError(
                f"MsgPack serialization failed: {exc}"
            ) from exc

    async def deserialize(self, value: str) -> Any:
        """Deserialize a Base64-encoded MessagePack string back to a Python value.

        Args:
            value: A Base64-encoded string produced by :meth:`serialize`.

        Returns:
            The deserialized Python value.

        Raises:
            CacheSerializationError: If deserialization fails.
        """
        import base64

        import msgpack

        try:
            packed = base64.b64decode(value)
            return await asyncio.to_thread(
                msgpack.unpackb,
                packed,
                raw=self._raw,
            )
        except (ValueError, TypeError, msgpack.UnpackException) as exc:
            raise CacheSerializationError(
                f"MsgPack deserialization failed: {exc}"
            ) from exc


__all__ = ["MsgPackSerializer"]
