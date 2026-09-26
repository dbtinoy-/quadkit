"""
Serialization module for Quadkit Cache.

This module provides various serialization implementations for cache backends,
allowing developers to choose the appropriate serialization strategy based on
their needs (interoperability vs. performance vs. compatibility).

The AsyncStringSerializerProtocol protocol is defined in quadkit.contracts.serialization
and implemented by cache-specific serializers in this module.
"""

from __future__ import annotations

from quadkit.cache.exceptions import CacheSerializationError
from quadkit.cache.serialization.compression import CompressingSerializer
from quadkit.cache.serialization.json import JSONSerializer
from quadkit.cache.serialization.msgpack import MsgPackSerializer
from quadkit.cache.serialization.type_registry import DEFAULT_REGISTRY, TypeRegistry
from quadkit.contracts.core.serialization import AsyncStringSerializerProtocol

__all__ = [
    "DEFAULT_REGISTRY",
    "AsyncStringSerializerProtocol",
    "CacheSerializationError",
    "CompressingSerializer",
    "JSONSerializer",
    "MsgPackSerializer",
    "TypeRegistry",
]
