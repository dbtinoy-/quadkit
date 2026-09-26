"""MySQL backend: connection, pool, and factory."""

from __future__ import annotations

from quadkit.sql.backends.mysql._connection import MySQLConnection
from quadkit.sql.backends.mysql._pool import (
    HAS_MYSQL,
    MySQLConnectionPool,
    create_mysql_pool,
)
from quadkit.sql.backends.mysql._shims import HAS_MYSQL as _HAS_MYSQL_SOURCE

__all__ = ["HAS_MYSQL", "MySQLConnection", "MySQLConnectionPool", "create_mysql_pool"]
