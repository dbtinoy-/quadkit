"""Database backend contract for the CLI database registry.

Defines ``QueryResult`` and the abstract ``DatabaseBackend`` interface
implemented by the concrete driver backends in ``database.py``.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from quadkit.contracts.data.sql.database import DatabaseProviderProtocol


@dataclass
class QueryResult:
    """Result of a database query."""

    rows: list[dict[str, Any]]
    rowcount: int


class DatabaseBackend(abc.ABC):
    """Abstract base class for database backends."""

    name: ClassVar[str]
    aliases: ClassVar[list[str]] = []

    @abc.abstractmethod
    def parse_url(self, url: str) -> dict[str, Any]:
        """Parse a database URL into connection parameters."""

    @abc.abstractmethod
    def get_client_binary(self) -> str | None:
        """Get the path to the native client binary."""

    @abc.abstractmethod
    def build_shell_command(self, params: dict[str, Any]) -> list[str]:
        """Build the command to launch the interactive shell."""

    @abc.abstractmethod
    async def get_tables(self, provider: DatabaseProviderProtocol) -> list[str]:
        """Get list of tables in the database."""

    @abc.abstractmethod
    async def get_columns(
        self, provider: DatabaseProviderProtocol, table: str
    ) -> list[dict[str, Any]]:
        """Get column information for a table."""

    @abc.abstractmethod
    def build_backup_command(
        self,
        params: dict[str, Any],
        output_path: str,
    ) -> list[str]:
        """Build command to backup the database."""

    @abc.abstractmethod
    def build_restore_command(
        self,
        params: dict[str, Any],
        input_path: str,
    ) -> list[str]:
        """Build command to restore the database."""

    def supports_backup(self) -> bool:
        """Check if backup is supported."""
        return self.get_client_binary() is not None

    def supports_restore(self) -> bool:
        """Check if restore is supported."""
        return self.get_client_binary() is not None

    def subprocess_env(self, params: dict[str, Any]) -> dict[str, str]:
        """Environment for child processes launched from built commands.

        Backends whose client tools accept credentials via environment
        variables (e.g. ``MYSQL_PWD``) override this so secrets never
        appear in the child's argv, where any local user could read them
        via ``ps``.

        Args:
            params: Connection parameters (may include ``password``).

        Returns:
            The environment dict to pass to ``subprocess``.
        """
        import os

        return dict(os.environ)
