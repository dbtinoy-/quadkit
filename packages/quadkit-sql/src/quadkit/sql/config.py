"""Configuration models for Quadkit Database.

This module provides Domain models (from contracts) for configuring database
connections, pooling, and operations.

Example:
    from quadkit.sql.config import DatabaseConfig

    # From YAML
    config = DatabaseConfig.from_yaml("application.yaml")

    # From environment
    config = DatabaseConfig.from_env()  # reads QK_DB__* env vars

    # From URL
    config = DatabaseConfig.from_url("postgresql://user:pass@localhost/db")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, cast

from quadkit.config import BaseConfig
from quadkit.contracts.core import Duration
from quadkit.contracts.core.config import Environment
from quadkit.contracts.exceptions import ConfigurationError
from quadkit.domain import DomainModel
from quadkit.sql import constants as const
from quadkit.validation import ConfigDict, Field, SecretStr, model_validator


@dataclass(init=False)
class DatabaseBackendConfig(DomainModel):
    """Database backend/connection configuration."""

    url: SecretStr = Field(
        ..., description="Database connection URL (may contain credentials)"
    )

    @model_validator(mode="after")
    def validate_url(self) -> DatabaseBackendConfig:
        raw_url = self.url.get_secret_value()
        if raw_url.startswith(("/", ".")):
            return self

        valid_prefixes = (
            "sqlite",
            "postgresql",
            "postgres",
            "mysql",
            "mariadb",
            "oracle",
            "mssql",
            "custom",
        )
        if not any(raw_url.startswith(prefix) for prefix in valid_prefixes):
            raise ConfigurationError(
                f"Invalid database URL prefix. Must start with one of: {', '.join(valid_prefixes)}",
            )
        return self


@dataclass(init=False)
class DatabasePoolConfig(DomainModel):
    """Connection pool configuration."""

    min_size: int = Field(default=const.DEFAULT_POOL_MIN_SIZE, ge=0)
    max_size: int = Field(default=const.DEFAULT_POOL_MAX_SIZE, ge=1)
    max_overflow: int = Field(default=5, ge=0)
    recycle: int = Field(default=3600, ge=0)
    timeout: float = Field(default=const.DEFAULT_POOL_TIMEOUT, ge=1.0)
    acquire_timeout: Duration = Field(default=Duration.seconds(30))
    idle_timeout: Duration = Field(default=Duration.minutes(5))
    max_lifetime: Duration = Field(default=Duration.hours(1))

    @model_validator(mode="after")
    def validate_sizes(self) -> DatabasePoolConfig:
        if self.max_size < self.min_size:
            raise ConfigurationError("max_size must be >= min_size")
        return self


@dataclass(init=False)
class DatabaseOperationConfig(DomainModel):
    """Database operation configuration."""

    echo: bool = Field(default=False)
    statement_timeout: Duration = Field(default=Duration.seconds(60))


@dataclass(init=False)
class NamedDatabaseConfig(DomainModel):
    """Configuration for one named database backend in a multi-database setup.

    Used in ``DatabaseConfig.backends`` list. Each entry gets its own
    connection pool, health check, and optional migration runner.
    Resolved via ``Annotated[DatabaseProviderProtocol, Named(name)]``.
    """

    name: str = Field(
        ..., description="Unique name for this backend (e.g. 'maps', 'rag')"
    )
    backend: DatabaseBackendConfig = Field(
        ..., description="Connection URL and driver settings"
    )
    primary: bool = Field(
        default=False,
        description="When True, also binds to DatabaseProviderProtocol without a name",
    )
    pool: DatabasePoolConfig = Field(
        default_factory=lambda: DatabasePoolConfig(min_size=2),
        description=(
            "Connection pool settings for this backend. "
            "Defaults to min_size=2 (higher floor than the system default of 1) "
            "since named backends are always intentional multi-DB connections "
            "and benefit from at least two warm connections."
        ),
    )
    migration_dir: str | None = Field(
        default=None,
        description="Alembic migration directory for this database. None = no migrations.",
    )


@dataclass(init=False)
class DatabaseOutboxConfig(DomainModel):
    """Outbox pattern configuration."""

    enabled: bool = Field(default=True)
    poll_interval: Duration = Field(default=Duration.seconds(5))
    batch_max_age: Duration = Field(default=Duration.seconds(30))


@dataclass(init=False)
class DatabaseMigrationConfig(DomainModel):
    """Migration configuration."""

    lock_timeout: Duration = Field(default=Duration.seconds(30))


@dataclass(init=False)
class DatabaseConfig(BaseConfig):
    """Hierarchical root configuration for Quadkit Database.

    Attributes:
        name: Configuration name (default: "database")
        enabled: Whether the database module is enabled
        backend: Database backend/connection configuration
        pool: Connection pool settings
        operations: Database operation settings
        audit_hmac_key: Optional HMAC key (plain text or base64) for audit
            checksum signing. Set via ``QK_DB__AUDIT_HMAC_KEY``.
        backends: List of named database backend configurations. When non-empty,
            enables multi-DB mode. The entry with ``primary=True`` (or the first
            entry) is also bound without a name for backward compatibility.
    """

    config_section: ClassVar[str] = "sql"

    model_config = cast(
        "ConfigDict",
        {
            "env_prefix": const.ENV_PREFIX,
            "env_nested_delimiter": const.ENV_NESTED_DELIMITER,
            "extra": "ignore",
        },
    )

    name: str = "database"
    enabled: bool = True
    env: Environment | None = Field(None, description="Deployment environment")
    backend: DatabaseBackendConfig = Field(
        default_factory=lambda: DatabaseBackendConfig(url="sqlite:///data.db"),
    )
    pool: DatabasePoolConfig = Field(default_factory=DatabasePoolConfig)
    operations: DatabaseOperationConfig = Field(default_factory=DatabaseOperationConfig)
    outbox: DatabaseOutboxConfig = Field(default_factory=DatabaseOutboxConfig)
    migrations: DatabaseMigrationConfig = Field(default_factory=DatabaseMigrationConfig)
    audit_hmac_key: str | None = Field(
        default=None,
        description="HMAC key for audit checksum signing. Plain text or base64.",
    )
    backends: list[NamedDatabaseConfig] = Field(
        default_factory=list,
        description=(
            "Multi-database backends list. When non-empty, drives multi-DB mode. "
            "The entry with primary=True (or the first entry) also binds to "
            "DatabaseProviderProtocol without a name for backward compatibility."
        ),
    )

    @model_validator(mode="after")
    def validate_production_security(self) -> DatabaseConfig:
        """Block insecure database configurations in production."""
        if self.environment == Environment.PRODUCTION:
            url = self.backend.url.get_secret_value().lower()
            insecure_patterns = [
                ":password@",
                ":123456@",
                ":postgres@",
                ":root@",
                ":admin@",
                ":changeme@",
            ]
            if any(pattern in url for pattern in insecure_patterns):
                raise ConfigurationError(
                    "CRITICAL SECURITY ERROR: Default database password detected in PRODUCTION URL.\n"
                    "You MUST set a secure database URL via "
                    f"{const.ENV_PREFIX}BACKEND__URL.",
                )

            if url.startswith("sqlite"):
                pass

        return self

    @classmethod
    def from_url(cls, url: str, name: str = "database") -> DatabaseConfig:
        """Create a DatabaseConfig from a URL string."""
        return cls(name=name, backend=DatabaseBackendConfig(url=url))

    @classmethod
    def from_env(cls, prefix: str = const.ENV_PREFIX) -> DatabaseConfig:
        """Create a DatabaseConfig by reading ``{const.ENV_PREFIX}*`` environment variables.

        Environment variables are stripped of *prefix*, lowercased, and ``__``
        is treated as a nesting delimiter, so ``QK_SQL__BACKEND__URL``
        maps to ``backend.url``.

        Args:
            prefix: Environment variable prefix to strip. Defaults to
                ``"{const.ENV_PREFIX}"``.

        Returns:
            A ``DatabaseConfig`` populated from the current environment,
            falling back to field defaults for any unset variables.

        Example::

            # With QK_SQL__BACKEND__URL=postgresql://user:pass@host/db set:
            config = DatabaseConfig.from_env()
            assert config.backend.url.get_secret_value().startswith("postgresql")
        """
        from quadkit.config.lib.sources import ConfigLoader, EnvironmentConfigSource

        loader = ConfigLoader()
        loader.add_source(EnvironmentConfigSource(prefix))
        return loader.load_sync(cls)

    @classmethod
    def from_named(
        cls,
        entry: NamedDatabaseConfig,
        base: DatabaseConfig | None = None,
    ) -> DatabaseConfig:
        """Build a DatabaseConfig from a NamedDatabaseConfig.

        Args:
            entry: The named backend entry to convert.
            base: Optional root DatabaseConfig to inherit operation settings from.

        Returns:
            A DatabaseConfig suitable for constructing a DatabaseService.
        """
        return cls(
            name=entry.name,
            backend=entry.backend,
            pool=entry.pool,
            operations=base.operations
            if base is not None
            else DatabaseOperationConfig(),
            audit_hmac_key=base.audit_hmac_key if base is not None else None,
        )


# --- Component Compatibility Models ---


@dataclass(init=False)
class ComponentPostgresConfig(DomainModel):
    """Legacy compatibility for PostgreSQL component drivers."""

    dsn: str = Field(default="postgresql://localhost:5432/quadkit")
    state_table: str = Field(default="quadkit_state")
    lock_table: str = Field(default="quadkit_locks")
    min_pool_size: int = Field(default=1)
    max_pool_size: int = Field(default=10)
    command_timeout: float = Field(default=30.0)


@dataclass
class DataConfig:
    """Configuration for the abstract data access layer.

    Attributes:
        default_page_size: Default number of results per page for offset pagination.
        max_page_size: Maximum allowed page size to prevent unbounded queries.
        default_cursor_size: Default page size for cursor-based pagination.
    """

    default_page_size: int = const.DEFAULT_PAGE_SIZE
    max_page_size: int = const.MAX_PAGE_SIZE
    default_cursor_size: int = const.DEFAULT_CURSOR_SIZE


__all__ = [
    "ComponentPostgresConfig",
    "DataConfig",
    "DatabaseBackendConfig",
    "DatabaseConfig",
    "DatabaseOperationConfig",
    "DatabasePoolConfig",
    "NamedDatabaseConfig",
]
