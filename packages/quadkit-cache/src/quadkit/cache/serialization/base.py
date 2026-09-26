"""Serialization abstraction layer for Quadkit Cache.

This module provides cache-specific serialization extensions.
The base AsyncStringSerializerProtocol protocol is defined in quadkit.contracts.serialization.
"""

from __future__ import annotations

from typing import Any

from quadkit.contracts.core.serialization import AsyncStringSerializerProtocol
from quadkit.serialization import SerializationError


class CacheSerializationError(SerializationError):
    """Raised when cache serialization or deserialization fails.

    This is a cache-specific subclass of the base SerializationError.

    Example:
        ```python
        try:
            data = await serializer.serialize(value)
        except TypeError as e:
            raise CacheSerializationError(f"Failed to cache: {e}") from e
        ```
    """

    _code: str = "QK_ERR_CACHE_015"

    def __init__(
        self,
        message: str = "Cache serialization failed",
        **kwargs: Any,
    ) -> None:
        """Initialize cache serialization error.

        Args:
            message: Error message.
            **kwargs: Additional error context.
        """
        kwargs.pop("code", None)
        from quadkit.contracts.exceptions import QuadkitError

        QuadkitError.__init__(
            self,
            message,
            **kwargs,
        )


__all__ = ["AsyncStringSerializerProtocol", "CacheSerializationError"]
