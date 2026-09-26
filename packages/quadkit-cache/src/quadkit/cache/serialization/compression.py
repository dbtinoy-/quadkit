"""Cache serializer with automatic compression for large values.

Compresses values over threshold to save memory and bandwidth.
"""

from __future__ import annotations

import io
import pickle
from typing import Any
import zlib

from quadkit.cache import constants as const
from quadkit.cache.exceptions import CacheSerializationError
from quadkit.logging import get_logger

logger = get_logger(__name__)


class _RestrictedUnpickler(pickle.Unpickler):
    """Unpickler bound to a deny-by-default class allowlist."""

    def __init__(self, file: io.BytesIO, allowed_classes: set[type]) -> None:
        """Initialize the restricted unpickler.

        Args:
            file: Byte stream containing the pickle payload.
            allowed_classes: Classes whose ``(module, qualname)`` may be
                reconstructed.
        """
        super().__init__(file)
        self._allowed_classes = allowed_classes

    def find_class(self, module: str, name: str) -> type:
        """Resolve a global; only allowlisted classes are returned.

        Args:
            module: Module name requested by the pickle stream.
            name: Attribute name requested by the pickle stream.

        Returns:
            The requested class.

        Raises:
            pickle.UnpicklingError: If the requested global is not on the
                allowlist (fail closed).
        """
        for cls in self._allowed_classes:
            if cls.__module__ == module and cls.__qualname__ == name:
                return cls
        raise pickle.UnpicklingError(
            f"global '{module}.{name}' is forbidden on an untrusted cache payload",
        )


def _restricted_loads(payload: bytes, allowed_classes: set[type]) -> Any:
    """Deserialize *payload* with the restricted unpickler.

    Args:
        payload: The pickle stream.
        allowed_classes: Classes that may be reconstructed (deny-by-default:
            an empty set denies every class; cache data is not trusted input).
    """
    return _RestrictedUnpickler(io.BytesIO(payload), allowed_classes).load()


class CompressingSerializer:
    """AsyncStringSerializerProtocol with automatic compression for large values.

    Compresses values above size threshold to save memory.
    """

    # Compression markers
    MARKER_UNCOMPRESSED = const.COMPRESSION_MARKER_UNCOMPRESSED
    MARKER_COMPRESSED = const.COMPRESSION_MARKER_COMPRESSED

    def __init__(
        self,
        compression_threshold: int = const.DEFAULT_COMPRESSION_THRESHOLD,
        compression_level: int = const.DEFAULT_COMPRESSION_LEVEL,
        allowed_classes: tuple[type, ...] | None = None,
    ) -> None:
        """Initialize serializer.

        Args:
            compression_threshold: Compress values larger than this (bytes)
            compression_level: Compression level (1-9, higher = more compression)
            allowed_classes: Classes that may be reconstructed from cache
                payloads. Defaults to ``None`` — deny every class (fail
                closed).

        Note:
            Cache payloads may originate from an attacker-controlled store
            (e.g. a shared Redis). Reconstruction is deny-by-default: only
            explicitly allowlisted classes are ever resolved; plain builtin
            containers (dicts, lists, strings, numbers) always round-trip.
        """
        self._threshold = compression_threshold
        self._level = compression_level
        self._allowed_classes = set(allowed_classes or ())

    async def serialize(self, value: Any) -> str:
        """Serialize and optionally compress value.

        Args:
            value: Value to serialize

        Returns:
            Serialized string (possibly compressed)
        """
        import asyncio

        try:
            # Pickle first
            pickled = await asyncio.to_thread(
                pickle.dumps,
                value,
                protocol=pickle.HIGHEST_PROTOCOL,
            )

            original_size = len(pickled)

            # Check if should compress
            if original_size <= self._threshold:
                # Too small, don't compress
                compressed_data = self.MARKER_UNCOMPRESSED + pickled
            else:
                # Compress
                compressed = await asyncio.to_thread(
                    zlib.compress,
                    pickled,
                    level=self._level,
                )
                compressed_size = len(compressed)

                # Check if compression helped
                if compressed_size >= original_size:
                    # Compression made it bigger (or same), don't use
                    logger.debug(
                        "Compression ineffective: %s -> %s bytes",
                        original_size,
                        compressed_size,
                    )
                    compressed_data = self.MARKER_UNCOMPRESSED + pickled
                else:
                    # Use compressed version
                    compression_ratio = compressed_size / original_size

                    logger.debug(
                        "Compressed: %s -> %s bytes (%s of original)",
                        original_size,
                        compressed_size,
                        f"{compression_ratio:.2%}",
                    )
                    compressed_data = self.MARKER_COMPRESSED + compressed

            # Convert to hex string for storage
            return compressed_data.hex()

        except (pickle.PicklingError, TypeError, AttributeError, zlib.error) as e:
            raise CacheSerializationError(f"Failed to serialize value: {e}") from e

    async def deserialize(self, value: str) -> Any:
        """Deserialize and decompress if needed.

        Args:
            value: Serialized string

        Returns:
            Original value

        Raises:
            SerializationError: If deserialization fails
        """
        import asyncio

        try:
            # Decode from hex back to bytes
            data = bytes.fromhex(value)

            if not data:
                raise CacheSerializationError("Empty data")

            # Check compression marker
            marker = data[:1]
            payload = data[1:]

            if marker == self.MARKER_UNCOMPRESSED:
                # Not compressed
                return await asyncio.to_thread(
                    _restricted_loads, payload, self._allowed_classes
                )

            if marker == self.MARKER_COMPRESSED:
                # Decompress first
                decompressed = await asyncio.to_thread(zlib.decompress, payload)
                return await asyncio.to_thread(
                    _restricted_loads, decompressed, self._allowed_classes
                )

            raise CacheSerializationError(f"Invalid compression marker: {marker!r}")

        except (ValueError, pickle.UnpicklingError, TypeError, zlib.error) as e:
            raise CacheSerializationError(f"Failed to deserialize value: {e}") from e

    def get_stats(self) -> dict[str, Any]:
        """Get serializer statistics.

        Returns:
            Stats dict
        """
        return {
            "compression_threshold": self._threshold,
            "compression_level": self._level,
        }


__all__ = ["CompressingSerializer"]
