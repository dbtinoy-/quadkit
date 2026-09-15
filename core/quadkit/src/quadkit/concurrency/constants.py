"""Constants for the concurrency subsystem.

Typed defaults, magic strings, and environment-variable prefixes used
across the concurrency system.
"""

from __future__ import annotations

import importlib.metadata

try:
    __version__: str = importlib.metadata.version("quadkit")
except ImportError:
    __version__ = "0.0.0"


# -- Environment Variable Prefix -------------------------------------------

ENV_PREFIX: str = "QK_CONCURRENCY__"
ENV_NESTED_DELIMITER: str = "__"
"""Environment variable prefix for concurrency configuration."""

# -- Numeric Defaults -------------------------------------------------------

DEFAULT_CHANNEL_CAPACITY: int = 100
"""Default bounded-channel buffer size; consumed by: Channel.__init__."""

DEFAULT_SEMAPHORE_TIMEOUT: float = 30.0
"""Default semaphore acquisition timeout in seconds; consumed by: Semaphore default."""

DEFAULT_WORKER_THREADS: int = 4
"""Default thread-pool size; consumed by: thread pool executor in Dispatcher."""

DEFAULT_DISPATCHER_SHUTDOWN_TIMEOUT: float = 10.0
"""Default shutdown drain timeout in seconds; consumed by: Dispatcher.stop()."""

__all__ = [
    "DEFAULT_CHANNEL_CAPACITY",
    "DEFAULT_DISPATCHER_SHUTDOWN_TIMEOUT",
    "DEFAULT_SEMAPHORE_TIMEOUT",
    "DEFAULT_WORKER_THREADS",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "__version__",
]
