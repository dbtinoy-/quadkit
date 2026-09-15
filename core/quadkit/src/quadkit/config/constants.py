"""Constants for the config subsystem.

Typed defaults and magic strings used across the configuration loading system.
"""

from __future__ import annotations

import importlib.metadata

__version__: str
try:
    __version__ = importlib.metadata.version("quadkit")
except ImportError:
    __version__ = "0.0.0"


# -- Environment Variable Prefix -------------------------------------------

ENV_PREFIX: str = "QK_CONFIG__"
ENV_NESTED_DELIMITER: str = "__"
"""Environment variable prefix for config configuration."""

# -- Config Loading Defaults -----------------------------------------------

DEFAULT_CONFIG_FILENAMES: list[str] = [
    "application.yml",
    "application.yaml",
]
"""Default filenames searched for when loading file-based config."""

DEFAULT_ENV_VAR_PREFIX: str = "QK_"
"""Prefix for environment variables used by the env-source loader."""

SUPPORTED_FORMATS: frozenset[str] = frozenset({"yaml", "yml", "json"})
"""File extensions understood by the config file loader."""

DEFAULT_RELOAD_INTERVAL: float = 30.0
"""Seconds between config live-reload checks; consumed by: ConfigWatcher."""

# -- Secret Detection ----------------------------------------------------------

INSECURE_SECRET_VALUES: frozenset[str] = frozenset(
    {
        "your-",
        "change-me",
        "changeme",
        "changeit",
        "placeholder",
        "xxx",
        "secret",
        "password",
        "example",
        "default",
        "replace-me",
        "todo",
        "fixme",
        "dummy",
        "test",
        "dev",
    }
)
"""Substrings that indicate a secret value has not been changed from its default."""

SECRET_FIELD_PATTERNS: frozenset[str] = frozenset(
    {
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "private_key",
        "credentials",
        "auth",
        "access_key",
        "signing_key",
        "encryption_key",
    }
)
"""Field-name substrings that identify a field as secret-bearing."""


__all__ = [
    "DEFAULT_CONFIG_FILENAMES",
    "DEFAULT_ENV_VAR_PREFIX",
    "DEFAULT_RELOAD_INTERVAL",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "INSECURE_SECRET_VALUES",
    "SECRET_FIELD_PATTERNS",
    "SUPPORTED_FORMATS",
    "__version__",
]
