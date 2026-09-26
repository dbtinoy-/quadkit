"""Base classes and exceptions for Quadkit DB migrations using Hollow Interfaces protocols"""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from quadkit.contracts.data.sql.database import DatabaseProviderProtocol
from quadkit.sql.exceptions import MigrationError


class MigrationDependencyError(MigrationError):
    """Raised when migration dependencies are not satisfied."""

    _code: str = "QK_ERR_SQL_032"


class MigrationExecutionError(MigrationError):
    """Raised when migration execution fails."""

    _code: str = "QK_ERR_SQL_033"


class MigrationNotFoundError(MigrationError):
    """Raised when a migration is not found."""

    _code: str = "QK_ERR_SQL_034"


class MigrationValidationError(MigrationError):
    """Raised when migration validation fails."""

    _code: str = "QK_ERR_SQL_035"


class Migration:
    """Abstract base class for migrations"""

    def __init__(self, version: str, description: str):
        self.version = version
        self.description = description
        self.id = f"{version}_{hash(self)}"

    @abstractmethod
    async def up(self, provider: DatabaseProviderProtocol) -> None:
        """Execute the upgrade migration"""

    @abstractmethod
    async def down(self, provider: DatabaseProviderProtocol) -> None:
        """Execute the downgrade migration"""


class SQLMigration(Migration):
    """SQL-based migration"""

    def __init__(self, version: str, description: str, up_sql: str, down_sql: str):
        super().__init__(version, description)
        self.up_sql = up_sql
        self.down_sql = down_sql

    async def up(self, provider: DatabaseProviderProtocol) -> None:
        """Execute upgrade SQL"""
        result = await provider.execute_query(self.up_sql)
        if not result.success:
            raise MigrationError(f"Migration up failed: {result.error_message}")

    async def down(self, provider: DatabaseProviderProtocol) -> None:
        """Execute downgrade SQL"""
        result = await provider.execute_query(self.down_sql)
        if not result.success:
            raise MigrationError(f"Migration down failed: {result.error_message}")


class PythonMigration(Migration):
    """Python-based migration"""

    def __init__(
        self,
        version: str,
        description: str,
        up_func: Callable[[DatabaseProviderProtocol], Awaitable[Any]],
        down_func: Callable[[DatabaseProviderProtocol], Awaitable[Any]],
    ) -> None:
        super().__init__(version, description)
        self.up_func = up_func
        self.down_func = down_func

    async def up(self, provider: DatabaseProviderProtocol) -> None:
        """Execute upgrade function"""
        await self.up_func(provider)

    async def down(self, provider: DatabaseProviderProtocol) -> None:
        """Execute downgrade function"""
        await self.down_func(provider)


class MigrationRecord:
    """Record of an applied migration"""

    def __init__(
        self,
        migration_id: str,
        version: str,
        description: str,
        applied_at: str,
        checksum: str,
    ):
        self.migration_id = migration_id
        self.version = version
        self.description = description
        self.applied_at = applied_at
        self.checksum = checksum

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MigrationRecord":
        """Create record from dictionary"""
        return cls(
            migration_id=data["migration_id"],
            version=data["version"],
            description=data["description"],
            applied_at=data["applied_at"],
            checksum=data["checksum"],
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert record to dictionary"""
        return {
            "migration_id": self.migration_id,
            "version": self.version,
            "description": self.description,
            "applied_at": self.applied_at,
            "checksum": self.checksum,
        }
