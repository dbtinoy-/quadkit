"""Configuration for the serialization subsystem.

Contains :class:`SerializationConfig`, which is consumed by providers
that set up the active JSON backend and encoding parameters.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from quadkit.serialization.constants import DEFAULT_ENCODING, DEFAULT_ENSURE_ASCII
from quadkit.serialization.types import JSONBackend


@dataclass(frozen=True)
class SerializationConfig:
    """JSON serialization configuration."""

    preferred_backend: JSONBackend = field(
        default=JSONBackend.ORJSON
    )  # consumed by: backend selection at startup
    encoding: str = DEFAULT_ENCODING  # consumed by: json serializer encode/decode
    ensure_ascii: bool = DEFAULT_ENSURE_ASCII  # consumed by: stdlib JSON fallback
    indent: int | None = None  # consumed by: pretty-print output — forward


__all__ = ["SerializationConfig"]
