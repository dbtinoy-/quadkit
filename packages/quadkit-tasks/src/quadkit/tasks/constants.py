"""Constants for quadkit-tasks."""

from __future__ import annotations

import importlib.metadata

# -- Version -------------------------------------------------------------------

try:
    __version__: str = importlib.metadata.version("quadkit-tasks")
except ImportError:
    __version__ = "0.0.0"

# -- Environment Variable Prefixes -------------------------------------------

ENV_PREFIX: str = "QK_TASKS__"
ENV_NESTED_DELIMITER: str = "__"

# -- Default Configuration Values --------------------------------------------

DEFAULT_BACKEND: str = "memory"
DEFAULT_QUEUE_NAME: str = "tasks"
DEFAULT_WORKER_COUNT: int = 1
DEFAULT_MAX_CONCURRENT_TASKS: int = 10
DEFAULT_POLL_INTERVAL: float = 0.1
DEFAULT_SHUTDOWN_TIMEOUT: float = 30.0
DEFAULT_TASK_TIMEOUT: float = 300.0
DEFAULT_MAX_TIMEOUT: float = 3600.0
DEFAULT_SCHEDULER_TIMEZONE: str = "UTC"
DEFAULT_SCHEDULER_CHECK_INTERVAL: float = 1.0

# -- Backend Names -----------------------------------------------------------

BACKEND_MEMORY: str = "memory"
BACKEND_REDIS: str = "redis"
BACKEND_RABBITMQ: str = "rabbitmq"
BACKEND_POSTGRES: str = "postgres"

# -- Default Connection Strings ----------------------------------------------

DEFAULT_REDIS_URL: str = "redis://localhost:6379"
DEFAULT_AMQP_URL: str = "amqp://localhost:5672/"

__all__ = [
    "BACKEND_MEMORY",
    "BACKEND_POSTGRES",
    "BACKEND_RABBITMQ",
    "BACKEND_REDIS",
    "DEFAULT_AMQP_URL",
    "DEFAULT_BACKEND",
    "DEFAULT_MAX_CONCURRENT_TASKS",
    "DEFAULT_MAX_TIMEOUT",
    "DEFAULT_POLL_INTERVAL",
    "DEFAULT_QUEUE_NAME",
    "DEFAULT_REDIS_URL",
    "DEFAULT_SCHEDULER_CHECK_INTERVAL",
    "DEFAULT_SCHEDULER_TIMEZONE",
    "DEFAULT_SHUTDOWN_TIMEOUT",
    "DEFAULT_TASK_TIMEOUT",
    "DEFAULT_WORKER_COUNT",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
]
