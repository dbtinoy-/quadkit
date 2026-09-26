"""Cache configuration loaders."""

from __future__ import annotations

import os
import re
from typing import Any

from quadkit.cache import constants as const
from quadkit.cache.config.top_level import CacheConfig
from quadkit.serialization import loads as json_loads


class EnvironmentConfigLoader:
    """Loader for cache configuration from various sources."""

    @staticmethod
    def from_env(prefix: str = const.ENV_PREFIX) -> CacheConfig:
        """Load CacheConfig from environment variables.

        Args:
            prefix: Environment variable prefix.

        Returns:
            Populated :class:`CacheConfig` instance.
        """
        upper_prefix = prefix.upper()
        flat: dict[str, Any] = {}
        for key, value in os.environ.items():
            if not key.startswith(upper_prefix):
                continue
            config_key = key[len(upper_prefix) :].lower()
            try:
                parsed: Any = int(value)
            except ValueError:
                try:
                    parsed = float(value)
                except ValueError:
                    parsed = value
            flat[config_key] = parsed
        result: dict[str, Any] = {}
        indexed: dict[str, dict[int, dict[str, Any]]] = {}
        for key, value in flat.items():
            # Nested-list entries use the env nested delimiter on both sides
            # of the index, e.g. ``backends__0__name`` → base ``backends``,
            # index ``0``, field ``name``.  The field is already plural in
            # the config model, so the list key is the base as-is.
            m = re.match(r"^(.+?)__(\d+)__(.+)$", key)
            if m:
                base, idx_str, suffix = m.group(1), m.group(2), m.group(3)
                list_key = base
                indexed.setdefault(list_key, {}).setdefault(int(idx_str), {})[
                    suffix
                ] = value
            else:
                result[key] = value
        for list_key, by_index in indexed.items():
            max_idx = max(by_index.keys())
            result[list_key] = [by_index.get(i, {}) for i in range(max_idx + 1)]
        return CacheConfig(**result)

    @staticmethod
    def from_dict(config_dict: dict[str, Any]) -> CacheConfig:
        """Load CacheConfig from a dictionary.

        Args:
            config_dict: Configuration dictionary.

        Returns:
            Populated :class:`CacheConfig` instance.
        """
        return CacheConfig(**config_dict)

    @staticmethod
    def from_yaml(file_path: str) -> CacheConfig:
        """Load CacheConfig from a YAML file.

        Args:
            file_path: Path to the YAML configuration file.

        Returns:
            Populated :class:`CacheConfig` instance.
        """
        try:
            import yaml
        except ImportError as e:
            raise ImportError(const.ERROR_MSG_PYYAML_INSTALL) from e
        with open(file_path, encoding=const.DEFAULT_ENCODING) as f:
            config_dict = yaml.safe_load(f)
        return CacheConfig(**config_dict)

    @staticmethod
    def from_json(file_path: str) -> CacheConfig:
        """Load CacheConfig from a JSON file.

        Args:
            file_path: Path to the JSON configuration file.

        Returns:
            Populated :class:`CacheConfig` instance.
        """
        with open(file_path, encoding=const.DEFAULT_ENCODING) as f:
            content = f.read()
        config_dict = json_loads(content)
        return CacheConfig(**config_dict)


__all__ = [
    "EnvironmentConfigLoader",
]
