"""Lazy loader implementation for quadkit-sql providers."""

from __future__ import annotations

from importlib import import_module
from typing import Any


def _lazy_import(name: str) -> Any:
    """Lazy import helper for optional provider classes."""
    module_map = {
        "PostgresProvider": "quadkit.sql.providers.postgres_provider",
        "MySQLProvider": "quadkit.sql.providers.mysql_provider",
    }

    if name not in module_map:
        raise AttributeError(name)

    mod_name = module_map[name]
    try:
        mod = import_module(mod_name)
        return getattr(mod, name)
    except (ImportError, AttributeError) as e:
        raise ImportError(f"Optional provider {name} is not available: {e}") from e
