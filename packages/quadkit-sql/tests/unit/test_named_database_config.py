"""Tests for NamedDatabaseConfig and DatabaseConfig.backends field."""
from __future__ import annotations

import pytest

from quadkit.sql.config import (
    DatabaseBackendConfig,
    DatabaseConfig,
    DatabaseOperationConfig,
    DatabasePoolConfig,
    NamedDatabaseConfig,
)


def test_named_database_config_minimal() -> None:
    """NamedDatabaseConfig requires name and backend.url."""
    cfg = NamedDatabaseConfig(
        name="maps",
        backend=DatabaseBackendConfig(url="postgresql+asyncpg://host/maps_db"),
    )
    assert cfg.name == "maps"
    assert cfg.primary is False
    assert cfg.migration_dir is None
    assert cfg.pool.min_size == 2  # default


def test_named_database_config_primary_flag() -> None:
    """primary=True marks the entry as the default binding."""
    cfg = NamedDatabaseConfig(
        name="primary",
        backend=DatabaseBackendConfig(url="postgresql+asyncpg://host/main"),
        primary=True,
        migration_dir="migrations",
    )
    assert cfg.primary is True
    assert cfg.migration_dir == "migrations"


def test_database_config_backends_default_empty() -> None:
    """DatabaseConfig.backends defaults to empty list."""
    cfg = DatabaseConfig(
        backend=DatabaseBackendConfig(url="sqlite:///test.db")
    )
    assert cfg.backends == []


def test_database_config_with_backends() -> None:
    """DatabaseConfig accepts backends list."""
    cfg = DatabaseConfig(
        backends=[
            NamedDatabaseConfig(
                name="primary",
                backend=DatabaseBackendConfig(url="sqlite:///primary.db"),
                primary=True,
                migration_dir="migrations",
            ),
            NamedDatabaseConfig(
                name="maps",
                backend=DatabaseBackendConfig(url="sqlite:///maps.db"),
                pool=DatabasePoolConfig(min_size=1, max_size=5),
            ),
        ]
    )
    assert len(cfg.backends) == 2
    assert cfg.backends[0].name == "primary"
    assert cfg.backends[1].name == "maps"
    assert cfg.backends[1].pool.max_size == 5


def test_database_config_from_named() -> None:
    """DatabaseConfig.from_named() builds a DatabaseConfig from NamedDatabaseConfig."""
    entry = NamedDatabaseConfig(
        name="rag",
        backend=DatabaseBackendConfig(url="postgresql+asyncpg://host/rag"),
        pool=DatabasePoolConfig(min_size=1, max_size=5),
    )
    cfg = DatabaseConfig.from_named(entry)
    assert cfg.name == "rag"
    assert cfg.backend.url.get_secret_value() == "postgresql+asyncpg://host/rag"
    assert cfg.pool.max_size == 5


def test_database_config_from_named_inherits_base() -> None:
    """from_named() inherits operations and audit_hmac_key from base."""
    entry = NamedDatabaseConfig(
        name="rag",
        backend=DatabaseBackendConfig(url="postgresql+asyncpg://host/rag"),
    )
    base = DatabaseConfig(
        backend=DatabaseBackendConfig(url="sqlite:///main.db"),
        operations=DatabaseOperationConfig(echo=True),
        audit_hmac_key="test-hmac-key",
    )
    cfg = DatabaseConfig.from_named(entry, base=base)
    assert cfg.name == "rag"
    assert cfg.operations.echo is True
    assert cfg.audit_hmac_key == "test-hmac-key"
    assert cfg.backends == []  # not propagated from base
