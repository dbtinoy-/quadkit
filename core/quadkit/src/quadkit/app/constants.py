"""Constants for the app subsystem.

Typed defaults for application lifecycle, naming, and health-check timeouts.
"""

from __future__ import annotations

import importlib.metadata

__version__: str
try:
    __version__ = importlib.metadata.version("quadkit")
except ImportError:
    __version__ = "0.0.0"


# -- Environment Variable Prefix -------------------------------------------

ENV_PREFIX: str = "QK_APP__"
ENV_NESTED_DELIMITER: str = "__"
"""Environment variable prefix for app configuration."""

# -- Application Defaults --------------------------------------------------

DEFAULT_APP_NAME: str = "quadkit-app"
"""Default application service name; consumed by: AppConfig.app_name, OTEL resource attribute."""

DEFAULT_SHUTDOWN_TIMEOUT: float = 30.0
"""Maximum seconds to wait for graceful shutdown; consumed by: Application.stop()."""

DEFAULT_HEALTH_CHECK_TIMEOUT: float = 5.0
"""Per-check timeout in seconds; consumed by: CoreProvider.health_check()."""

__all__ = [
    "DEFAULT_APP_NAME",
    "DEFAULT_HEALTH_CHECK_TIMEOUT",
    "DEFAULT_SHUTDOWN_TIMEOUT",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "__version__",
]
