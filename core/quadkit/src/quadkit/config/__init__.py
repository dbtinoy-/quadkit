"""Quadkit Config — Configuration loading, models, and sources.

This module uses lazy imports for all public symbols to keep
import overhead minimal.  Every name listed in _LAZY_IMPORTS
is available at package level:

    from quadkit.config import <Symbol>

or by accessing the attribute on the package:

    import quadkit.config as config
    config.<Symbol>
"""

from __future__ import annotations

__path__ = __import__("pkgutil").extend_path(__path__, __name__)

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from quadkit.config.base import BaseConfig
    from quadkit.config.constants import (
        DEFAULT_CONFIG_FILENAMES as DEFAULT_CONFIG_FILENAMES,
    )
    from quadkit.config.constants import (
        DEFAULT_ENV_VAR_PREFIX as DEFAULT_ENV_VAR_PREFIX,
    )
    from quadkit.config.constants import (
        DEFAULT_RELOAD_INTERVAL as DEFAULT_RELOAD_INTERVAL,
    )
    from quadkit.config.constants import (
        INSECURE_SECRET_VALUES as INSECURE_SECRET_VALUES,
    )
    from quadkit.config.constants import (
        SECRET_FIELD_PATTERNS as SECRET_FIELD_PATTERNS,
    )
    from quadkit.config.constants import (
        SUPPORTED_FORMATS as SUPPORTED_FORMATS,
    )
    from quadkit.config.exceptions import (
        ConfigReloadError as ConfigReloadError,
    )
    from quadkit.config.exceptions import (
        ConfigSectionNotFoundError as ConfigSectionNotFoundError,
    )
    from quadkit.config.exceptions import (
        ConfigSourceError as ConfigSourceError,
    )
    from quadkit.config.exceptions import (
        ConfigurationError as ConfigurationError,
    )
    from quadkit.config.lib.merge import deep_merge as deep_merge
    from quadkit.config.lib.merge import interpolate_env_vars as interpolate_env_vars
    from quadkit.config.lib.merge import interpolate_string as interpolate_string
    from quadkit.config.lib.registry import ConfigRegistry
    from quadkit.config.lib.sources import (
        CliConfigSource,
        ConfigLoader,
        ConfigSource,
        DirectoryConfigSource,
        DotEnvSource,
        EnvironmentConfigSource,
        FileConfigSource,
    )
    from quadkit.config.lib.validation import is_insecure_secret as is_insecure_secret
    from quadkit.config.lib.validation import (
        validate_all_configs as validate_all_configs,
    )
    from quadkit.config.lib.watcher import ConfigWatcher
    from quadkit.config.main import QuadkitConfig
    from quadkit.config.protocols import ConfigSourceProtocol as ConfigSourceProtocol
    from quadkit.config.secrets import DEFAULT_MIN_LENGTHS as DEFAULT_MIN_LENGTHS
    from quadkit.config.secrets import (
        DEFAULT_PLACEHOLDER_VALUES as DEFAULT_PLACEHOLDER_VALUES,
    )
    from quadkit.config.secrets import SecretsPolicy as SecretsPolicy
    from quadkit.config.secrets import SecretsValidator as SecretsValidator
    from quadkit.config.secrets import (
        SecretsValidatorProtocol as SecretsValidatorProtocol,
    )
    from quadkit.config.secrets import SecretViolation as SecretViolation
    from quadkit.config.types import ConfigSourceType as ConfigSourceType
    from quadkit.contracts.core.config import ConfigIssue as ConfigIssue
    from quadkit.contracts.core.config import Environment as Environment
    from quadkit.contracts.exceptions import ConfigurationError
    from quadkit.logging.config import LoggingConfig, SamplingConfig

_LAZY_IMPORTS: dict[str, str] = {
    "BaseConfig": "quadkit.config.base",
    "CliConfigSource": "quadkit.config.lib.sources",
    "ConfigIssue": "quadkit.contracts.core.config",
    "ConfigLoader": "quadkit.config.lib.sources",
    "ConfigRegistry": "quadkit.config.lib.registry",
    "ConfigSource": "quadkit.config.lib.sources",
    "ConfigWatcher": "quadkit.config.lib.watcher",
    "ConfigurationError": "quadkit.contracts.exceptions",
    "DirectoryConfigSource": "quadkit.config.lib.sources",
    "DotEnvSource": "quadkit.config.lib.sources",
    "Environment": "quadkit.contracts.core.config",
    "EnvironmentConfigSource": "quadkit.config.lib.sources",
    "FileConfigSource": "quadkit.config.lib.sources",
    "QuadkitConfig": "quadkit.config.main",
    "LoggingConfig": "quadkit.logging.config",
    "SamplingConfig": "quadkit.logging.config",
    "deep_merge": "quadkit.config.lib.merge",
    "interpolate_env_vars": "quadkit.config.lib.merge",
    "interpolate_string": "quadkit.config.lib.merge",
    "validate_all_configs": "quadkit.config.lib.validation",
    # secrets
    "DEFAULT_MIN_LENGTHS": "quadkit.config.secrets",
    "DEFAULT_PLACEHOLDER_VALUES": "quadkit.config.secrets",
    "SecretViolation": "quadkit.config.secrets",
    "SecretsPolicy": "quadkit.config.secrets",
    "SecretsValidator": "quadkit.config.secrets",
    "SecretsValidatorProtocol": "quadkit.config.secrets",
    # constants
    "DEFAULT_CONFIG_FILENAMES": "quadkit.config.constants",
    "DEFAULT_ENV_VAR_PREFIX": "quadkit.config.constants",
    "DEFAULT_RELOAD_INTERVAL": "quadkit.config.constants",
    "INSECURE_SECRET_VALUES": "quadkit.config.constants",
    "SECRET_FIELD_PATTERNS": "quadkit.config.constants",
    "SUPPORTED_FORMATS": "quadkit.config.constants",
    "is_insecure_secret": "quadkit.config.lib.validation",
    # exceptions
    "ConfigReloadError": "quadkit.config.exceptions",
    "ConfigSectionNotFoundError": "quadkit.config.exceptions",
    "ConfigSourceError": "quadkit.config.exceptions",
    # protocols
    "ConfigSourceProtocol": "quadkit.config.protocols",
    # types
    "ConfigSourceType": "quadkit.config.types",
    # provider
    "ConfigProvider": "quadkit.config.di.provider",
}


def __getattr__(name: str) -> Any:
    if name in _LAZY_IMPORTS:
        import importlib

        module = importlib.import_module(_LAZY_IMPORTS[name])
        value = getattr(module, name)
        globals()[name] = value
        return value
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    return list(_LAZY_IMPORTS.keys())


__all__ = (
    "DEFAULT_CONFIG_FILENAMES",
    "DEFAULT_ENV_VAR_PREFIX",
    "DEFAULT_MIN_LENGTHS",
    "DEFAULT_PLACEHOLDER_VALUES",
    "DEFAULT_RELOAD_INTERVAL",
    "INSECURE_SECRET_VALUES",
    "SECRET_FIELD_PATTERNS",
    "SUPPORTED_FORMATS",
    "BaseConfig",
    "CliConfigSource",
    "ConfigIssue",
    "ConfigLoader",
    "ConfigRegistry",
    "ConfigReloadError",
    "ConfigSectionNotFoundError",
    "ConfigSource",
    "ConfigSourceError",
    "ConfigSourceProtocol",
    "ConfigSourceType",
    "ConfigWatcher",
    "ConfigurationError",
    "DirectoryConfigSource",
    "DotEnvSource",
    "Environment",
    "EnvironmentConfigSource",
    "FileConfigSource",
    "LoggingConfig",
    "QuadkitConfig",
    "SamplingConfig",
    "SecretViolation",
    "SecretsPolicy",
    "SecretsValidator",
    "SecretsValidatorProtocol",
    "deep_merge",
    "interpolate_env_vars",
    "interpolate_string",
    "is_insecure_secret",
    "validate_all_configs",
)
__version__ = "0.1.0"
