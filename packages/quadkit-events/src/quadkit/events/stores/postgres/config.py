"""PostgreSQL connection configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from quadkit.config.base import BaseConfig
from quadkit.validation import ConfigDict, Field, SecretStr, field_validator


@dataclass(init=False)
class PostgresEventStoreConfig(BaseConfig):
    """PostgreSQL connection configuration.

    Attributes:
        dsn: Database connection string (treated as a secret).
        pool_min_size: Minimum connection pool size.
        pool_max_size: Maximum connection pool size.
        command_timeout: Command timeout in seconds.
        events_table: Name of the events table.
        snapshots_table: Name of the snapshots table.
        auto_create_tables: Whether to create tables automatically.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    dsn: SecretStr | None = Field(
        default=None,
        description="PostgreSQL connection string. Optional when a DatabaseProviderProtocol is injected via DI.",
    )
    pool_min_size: int = Field(default=5, ge=1)
    pool_max_size: int = Field(default=20, ge=1)
    command_timeout: float = Field(default=60.0, ge=1.0)
    events_table: str = Field(default="events")
    snapshots_table: str = Field(default="snapshots")
    auto_create_tables: bool = Field(default=True)

    @field_validator("dsn", mode="before")
    @classmethod
    def validate_dsn(cls, v: SecretStr | str | None) -> SecretStr | None:
        """Validate and normalize the DSN. Returns None when not provided."""
        if v is None:
            return None
        raw = v.get_secret_value() if isinstance(v, SecretStr) else v
        normalized = raw
        if "+asyncpg" in raw:
            normalized = raw.replace("+asyncpg", "")
        elif "+psycopg2" in raw:
            normalized = raw.replace("+psycopg2", "")
        if not normalized.startswith(("postgresql://", "postgres://")):
            raise ValueError("DSN must start with postgresql:// or postgres://")
        return SecretStr(normalized)
