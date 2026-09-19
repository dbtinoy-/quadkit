"""Dict merging and env-var interpolation helpers for config loading.

These utilities are shared across config sources and the CLI config loader.
Import from here — do not redefine locally.
"""

from __future__ import annotations

import os
import re
from typing import Any

from quadkit.contracts.exceptions import ConfigurationError

# Compiled once at module level for performance
ENV_INTERPOLATION_RE: re.Pattern[str] = re.compile(r"\${([^}:]+)(?::([^}]*))?}")


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> None:
    """Recursively merge *overlay* into *base*, mutating *base* in place.

    Dicts are merged recursively; all other types are overwritten.

    Args:
        base: The dict to merge into.
        overlay: The dict whose values take precedence.
    """
    for key, value in overlay.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value


def interpolate_env_vars(config: dict[str, Any]) -> None:
    """Recursively interpolate ``${VAR}`` and ``${VAR:default}`` in strings.

    Mutates *config* in place.  String values that contain ``${VAR}`` syntax
    are resolved against the current process environment.

    Args:
        config: Configuration dict to process.
    """
    for key, value in config.items():
        if isinstance(value, dict):
            interpolate_env_vars(value)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    interpolate_env_vars(item)
                elif isinstance(item, str):
                    value[i] = interpolate_string(item)
        elif isinstance(value, str):
            config[key] = interpolate_string(value)


def interpolate_string(value: str) -> str:
    """Replace ``${VAR}`` / ``${VAR:default}`` placeholders with env values.

    ``${VAR}`` is replaced by the value of the environment variable ``VAR``.
    ``${VAR:default}`` uses ``default`` when ``VAR`` is not set.
    ``${VAR:}`` (explicit empty default) produces an empty string.

    Args:
        value: String potentially containing interpolation placeholders.

    Returns:
        String with all placeholders replaced by their resolved values.

    Raises:
        ConfigurationError: When a placeholder has no default and the
            environment variable is not set.
    """

    def _replace(match: re.Match[str]) -> str:
        var = match.group(1)
        default = match.group(2)
        env_value = os.environ.get(var)
        if env_value is not None:
            return env_value
        if default is not None:
            # Explicit default (may be empty string for ${VAR:})
            return default
        raise ConfigurationError(
            f"Missing required environment variable: {var!r}"
            f" (referenced as ${{{var}}} in configuration)"
        )

    return ENV_INTERPOLATION_RE.sub(_replace, value)


__all__ = [
    "ENV_INTERPOLATION_RE",
    "deep_merge",
    "interpolate_env_vars",
    "interpolate_string",
]
