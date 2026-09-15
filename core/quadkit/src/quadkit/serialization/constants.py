"""Constants for the serialization subsystem.

Runtime-detected backend name plus encoding defaults for the JSON layer.
"""

from __future__ import annotations

import importlib.metadata

try:
    __version__: str = importlib.metadata.version("quadkit")
except ImportError:
    __version__ = "0.0.0"


from quadkit.serialization.backends.json import (
    JSON_BACKEND as JSON_BACKEND,  # re-export; consumed by: SerializationConfig.preferred_backend default check
)

DEFAULT_ENCODING: str = "utf-8"  # consumed by: json serializer encode/decode
DEFAULT_ENSURE_ASCII: bool = False  # consumed by: stdlib JSON fallback

__all__ = [
    "DEFAULT_ENCODING",
    "DEFAULT_ENSURE_ASCII",
    "JSON_BACKEND",
    "__version__",
]
