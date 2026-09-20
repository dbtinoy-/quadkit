"""Constants for quadkit-cli."""

from __future__ import annotations

import importlib.metadata

# -- Version -------------------------------------------------------------------

__version__: str
try:
    __version__ = importlib.metadata.version("quadkit-cli")
except ImportError:
    __version__ = "0.0.0"

# -- Environment Variable Prefixes -------------------------------------------

ENV_PREFIX: str = "QK_CLI__"
ENV_NESTED_DELIMITER: str = "__"

# -- CLI Defaults ------------------------------------------------------------

DEFAULT_OUTPUT_FORMAT: str = "text"
DEFAULT_LOG_LEVEL: str = "INFO"
DEFAULT_CONFIG_FILE: str = "application.yaml"

# -- Output Formats ----------------------------------------------------------

FORMAT_TEXT: str = "text"
FORMAT_JSON: str = "json"
FORMAT_TABLE: str = "table"

__all__ = [
    "DEFAULT_CONFIG_FILE",
    "DEFAULT_LOG_LEVEL",
    "DEFAULT_OUTPUT_FORMAT",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "FORMAT_JSON",
    "FORMAT_TABLE",
    "FORMAT_TEXT",
    "__version__",
]
