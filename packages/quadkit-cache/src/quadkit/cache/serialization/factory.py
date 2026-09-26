"""AsyncStringSerializerProtocol helpers for provider initialization.

Encapsulate serializer creation so the provider is smaller and easier to test.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from quadkit.cache.serialization.json import JSONSerializer
from quadkit.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from quadkit.cache.protocols import CacheSerializerProtocol


def create_serializers() -> dict[str, CacheSerializerProtocol]:
    """Return available serializer instances keyed by name."""
    serializers: dict[str, CacheSerializerProtocol] = {
        "json": JSONSerializer(),  # type: ignore[dict-item]
    }

    # Optional MessagePack support when dependency is installed.
    try:
        from quadkit.cache.serialization.msgpack import MsgPackSerializer

        serializers["msgpack"] = MsgPackSerializer()  # type: ignore[assignment]
    except ImportError:
        logger.warning(
            "msgpack_not_installed",
            hint="pip install msgpack",
            detail="msgpack serializer disabled",
        )

    return serializers


__all__ = ["create_serializers"]
