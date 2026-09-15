"""Constants for the core identity subsystem."""

from __future__ import annotations

import importlib.metadata

from quadkit.contracts.core.identity import IdStrategy

try:
    __version__ = importlib.metadata.version("quadkit")
except ImportError:
    __version__ = "0.0.0"

DEFAULT_ID_STRATEGY: IdStrategy = IdStrategy.UUID4
DEFAULT_PREFIX_SEPARATOR: str = "_"
DEFAULT_ULID_LENGTH: int = 26

__all__ = [
    "DEFAULT_ID_STRATEGY",
    "DEFAULT_PREFIX_SEPARATOR",
    "DEFAULT_ULID_LENGTH",
    "__version__",
]
