"""Package-level constants for quadkit-sql.

These are stable, typed constants used across the SQL package.
Import from here — never hard-code these values elsewhere.
"""

from __future__ import annotations

import importlib.metadata

# -- Version -------------------------------------------------------------------

try:
    __version__: str = importlib.metadata.version("quadkit-sql")
except ImportError:
    __version__ = "0.0.0"


# ---------------------------------------------------------------------------
# Environment variable prefix
# ---------------------------------------------------------------------------

ENV_PREFIX: str = "QK_SQL__"
ENV_NESTED_DELIMITER: str = "__"
"""Delimiter for nested env var keys (e.g. QK_SQL__POOL__MAX_SIZE)."""


# ---------------------------------------------------------------------------
# Connection pool defaults
# ---------------------------------------------------------------------------

DEFAULT_POOL_MIN_SIZE: int = 1
DEFAULT_POOL_MAX_SIZE: int = 10
DEFAULT_POOL_TIMEOUT: float = 30.0
DEFAULT_CONNECT_TIMEOUT: float = 10.0
DEFAULT_COMMAND_TIMEOUT: float = 60.0

# ---------------------------------------------------------------------------
# Migration defaults
# ---------------------------------------------------------------------------

DEFAULT_MIGRATIONS_DIR: str = "migrations"
DEFAULT_MIGRATIONS_TABLE: str = "schema_migrations"

# ---------------------------------------------------------------------------
# Query defaults
# ---------------------------------------------------------------------------

DEFAULT_QUERY_TIMEOUT: float = 30.0
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_RETRY_DELAY: float = 0.5

# ---------------------------------------------------------------------------
# Backend identifiers
# ---------------------------------------------------------------------------

BACKEND_SQLITE: str = "sqlite"
BACKEND_POSTGRES: str = "postgres"
BACKEND_MYSQL: str = "mysql"

# ---------------------------------------------------------------------------
# Pagination defaults (moved from quadkit.data)
# ---------------------------------------------------------------------------

DEFAULT_PAGE_SIZE: int = 20
MAX_PAGE_SIZE: int = 1000
DEFAULT_CURSOR_SIZE: int = 20


__all__ = [
    "BACKEND_MYSQL",
    "BACKEND_POSTGRES",
    "BACKEND_SQLITE",
    "DEFAULT_COMMAND_TIMEOUT",
    "DEFAULT_CONNECT_TIMEOUT",
    "DEFAULT_CURSOR_SIZE",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MIGRATIONS_DIR",
    "DEFAULT_MIGRATIONS_TABLE",
    "DEFAULT_PAGE_SIZE",
    "DEFAULT_POOL_MAX_SIZE",
    "DEFAULT_POOL_MIN_SIZE",
    "DEFAULT_POOL_TIMEOUT",
    "DEFAULT_QUERY_TIMEOUT",
    "DEFAULT_RETRY_DELAY",
    "ENV_NESTED_DELIMITER",
    "ENV_PREFIX",
    "MAX_PAGE_SIZE",
]
