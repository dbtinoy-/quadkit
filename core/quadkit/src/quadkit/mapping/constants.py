"""Mapping constants — defaults and limits for the object-mapping subsystem."""

from __future__ import annotations

import importlib.metadata

# -- Version -------------------------------------------------------------------

try:
    __version__: str = importlib.metadata.version("quadkit")
except ImportError:
    __version__ = "0.0.0"


# ---------------------------------------------------------------------------
# Environment Variable Prefixes
# ---------------------------------------------------------------------------

ENV_PREFIX: str = "QK_MAPPING__"
"""Environment variable prefix for mapping configuration."""

ENV_NESTED_DELIMITER: str = "__"
"""Delimiter for nested env var keys."""


# Maximum allowed nesting depth for recursive object mapping.
MAX_MAPPING_DEPTH: int = 32

# Maximum number of mapping rules that can be registered per mapper instance.
MAX_MAPPING_RULES: int = 1024


__all__ = [
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "MAX_MAPPING_DEPTH",
    "MAX_MAPPING_RULES",
]
