"""Constants for the DI subsystem.

Typed defaults for container resolution depth and scope naming.
"""

from __future__ import annotations

import importlib.metadata

__version__: str
try:
    __version__ = importlib.metadata.version("quadkit")
except ImportError:
    __version__ = "0.0.0"


# -- Environment Variable Prefix -------------------------------------------

ENV_PREFIX: str = "QK_DI__"
ENV_NESTED_DELIMITER: str = "__"
"""Environment variable prefix for DI configuration."""

# -- Resolution Defaults ---------------------------------------------------

DEFAULT_MAX_RESOLUTION_DEPTH: int = 50
"""Maximum dependency resolution depth before declaring a cycle; consumed by: DIResolverProtocol."""

DEFAULT_SCOPE_NAME: str = "request"
"""Default scope name for request-scoped service registrations; consumed by: RequestScope."""

__all__ = [
    "DEFAULT_MAX_RESOLUTION_DEPTH",
    "DEFAULT_SCOPE_NAME",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "__version__",
]
