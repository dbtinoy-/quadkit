"""
JSON-based serializer implementation for Quadkit Cache.

This module provides high-performance JSON serialization using orjson (5-10x faster
than stdlib json) with enhanced type support for common Python types like datetime,
UUID, and custom objects.

"""

from __future__ import annotations

from typing import Any

from quadkit.cache.exceptions import CacheSerializationError
from quadkit.serialization import dumps, loads


class JSONSerializer:
    """
    High-performance JSON-based serializer with enhanced type support.

    Uses orjson (5-10x faster than stdlib json) for serialization with automatic
    fallback to stdlib json if orjson is unavailable.

    Supports serialization of:
    - Basic Python types (str, int, float, bool, None)
    - Collections (list, dict, tuple, set)
    - datetime and date objects (via orjson native support)
    - UUID objects (via orjson native support)
    - Custom objects with __dict__ attribute

    Performance:
    - With orjson: ~5-10x faster than stdlib json
    - Native support for datetime, UUID, dataclasses
    - Optimized for Redis/Memcached serialization workloads

    This class implements the AsyncStringSerializerProtocol protocol.
    """

    async def serialize(self, value: Any) -> str:
        """Serialize a Python object to JSON string using orjson (5-10x faster)."""
        import asyncio

        try:
            return await asyncio.to_thread(dumps, value)  # type: ignore[arg-type]
        except (TypeError, ValueError) as e:
            raise CacheSerializationError(f"Failed to serialize value: {e}") from e

    async def deserialize(self, value: str) -> Any:
        """Deserialize a JSON string back to a Python object."""
        import asyncio

        try:
            return await asyncio.to_thread(loads, value)
        except (ValueError, TypeError) as e:
            raise CacheSerializationError(f"Failed to deserialize value: {e}") from e
