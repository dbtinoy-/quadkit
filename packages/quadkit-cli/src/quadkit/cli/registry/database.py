"""Database backend registry with pluggable drivers.

This module provides a registry pattern for supporting multiple database backends.
Each backend is implemented as a separate class that handles connection, query,
and shell operations for that specific database type.

The backend contract (``QueryResult``, ``DatabaseBackend``) lives in
``backend_base``; the built-in engines live in ``database_backends``. Both are
re-exported here, because the registry is what the CLI talks to.
"""

from __future__ import annotations

import re
import subprocess
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self

from quadkit.cli.package_names import module_for
from quadkit.cli.registry.backend_base import (
    DatabaseBackend as DatabaseBackend,
)
from quadkit.cli.registry.backend_base import (
    QueryResult as QueryResult,
)
from quadkit.cli.registry.database_backends import (
    MySQLBackend as MySQLBackend,
)
from quadkit.cli.registry.database_backends import (
    PostgreSQLBackend as PostgreSQLBackend,
)
from quadkit.cli.registry.database_backends import (
    SQLiteBackend as SQLiteBackend,
)

if TYPE_CHECKING:
    from pathlib import Path


class DatabaseRegistry:
    """Registry for database backends.

    Instances are always empty — use :meth:`with_defaults` for the
    in-package built-ins or :meth:`register` for plugin backends.
    """

    def __init__(self) -> None:
        self._backends: dict[str, DatabaseBackend] = {}

    def register(self, backend: type[DatabaseBackend]) -> None:
        """Register a database backend."""
        instance = backend()
        self._backends[backend.name] = instance
        for alias in backend.aliases:
            self._backends[alias] = instance

    def get(self, name: str) -> DatabaseBackend | None:
        """Get a backend by name."""
        return self._backends.get(name)

    def get_all(self) -> dict[str, DatabaseBackend]:
        """Get all registered backends."""
        return self._backends.copy()

    def detect_from_url(self, url: str) -> DatabaseBackend:
        """Detect and return the appropriate backend from a database URL."""
        if url.startswith("sqlite"):
            return self._backends["sqlite"]

        match = re.match(r"^(\w+):", url)
        if match:
            backend_name = match.group(1).lower()
            if backend_name in self._backends:
                return self._backends[backend_name]

        for backend in self._backends.values():
            if backend.get_client_binary():
                return backend

        return self._backends["sqlite"]

    @classmethod
    def _default_entries(cls) -> tuple[type[DatabaseBackend], ...]:
        """The complete in-package built-in set, declared exactly once."""
        return (
            SQLiteBackend,
            PostgreSQLBackend,
            MySQLBackend,
        )

    @classmethod
    def with_defaults(cls) -> DatabaseRegistry:
        """Return an instance populated with the built-in backends."""
        registry = cls()
        for entry in cls._default_entries():
            registry.register(entry)
        return registry


class DatabaseConnection:
    """Database connection manager using the registry pattern."""

    def __init__(self, url: str | None = None, config_path: Path | None = None) -> None:
        self.url = url or self._get_url_from_env_or_config(config_path)
        self.backend = DatabaseRegistry.with_defaults().detect_from_url(self.url)
        self.params = self.backend.parse_url(self.url)
        self._provider: Any = None
        self._provider_async = None

    @staticmethod
    def _get_url_from_env_or_config(config_path: Path | None = None) -> str:
        import os

        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            return db_url

        if config_path and config_path.exists():
            import yaml

            with open(config_path) as f:
                config: dict[str, Any] = yaml.safe_load(f) or {}

            database_cfg = config.get("database")
            if isinstance(database_cfg, dict):
                database_url = database_cfg.get("url")
                if isinstance(database_url, str) and database_url:
                    return database_url

        return "sqlite:///./dev.db"

    async def connect(self) -> Any:
        """Connect to the database and return a provider."""
        try:
            import importlib

            db_providers = importlib.import_module(module_for("sql", "providers"))
            DatabaseService = db_providers.DatabaseService
            provider: Any = DatabaseService(config=self.url)
            self._provider = provider
            await provider.boot()
            return provider
        except ImportError as e:
            raise RuntimeError(
                f"The optional database provider is not installed: {e}"
            ) from e

    async def disconnect(self) -> None:
        """Disconnect from the database."""
        if self._provider is not None:
            await self._provider.shutdown()
            self._provider = None

    async def __aenter__(self) -> Self:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.disconnect()

    def open_shell(self) -> None:
        """Open the native database shell."""
        cmd = self.backend.build_shell_command(self.params)
        try:
            subprocess.run(  # noqa: S603 — registry-built argv list
                cmd,
                check=False,
                env=self.backend.subprocess_env(self.params),
            )
        except OSError as e:
            raise RuntimeError(f"Failed to open shell: {e}") from e

    async def get_tables(self) -> list[str]:
        """Get list of tables."""
        if self._provider is None:
            await self.connect()
        if self._provider is not None:
            tables: list[str] = await self.backend.get_tables(self._provider)
            return tables
        return []

    async def get_columns(self, table: str) -> list[dict[str, Any]]:
        """Get columns for a table."""
        if self._provider is None:
            await self.connect()
        if self._provider is not None:
            columns: list[dict[str, Any]] = await self.backend.get_columns(
                self._provider, table
            )
            return columns
        return []


def create_database_connection(
    url: str | None = None,
    config_path: Path | None = None,
) -> DatabaseConnection:
    """Factory function to create a database connection."""
    return DatabaseConnection(url=url, config_path=config_path)


__all__ = [
    "DatabaseBackend",
    "DatabaseConnection",
    "DatabaseRegistry",
    "MySQLBackend",
    "PostgreSQLBackend",
    "QueryResult",
    "SQLiteBackend",
    "create_database_connection",
]
