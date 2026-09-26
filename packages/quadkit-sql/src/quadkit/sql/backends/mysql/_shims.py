"""Optional-dependency shims shared by mysql backend modules."""

import importlib
from typing import Any

aiomysql: Any = None
try:
    aiomysql = importlib.import_module("aiomysql")
    HAS_MYSQL = True
except (ImportError, ModuleNotFoundError):
    # aiomysql not installed in this environment
    aiomysql = None
    HAS_MYSQL = False

# Fallback alias: Exception when aiomysql is unavailable
MySQLError: type = getattr(aiomysql, "Error", Exception)
