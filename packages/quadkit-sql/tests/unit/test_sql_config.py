"""Unit tests for quadkit.sql.config module."""

import os
from unittest.mock import patch

import pytest

from quadkit.contracts.exceptions import ConfigurationError
from quadkit.sql import config as sql_config
from quadkit.sql.config import (
    ComponentPostgresConfig,
    DataConfig,
    DatabaseBackendConfig,
    DatabaseConfig,
    DatabaseOperationConfig,
    DatabasePoolConfig,
    NamedDatabaseConfig,
)


class TestDatabaseBackendConfig:
    """Tests for DatabaseBackendConfig."""

    def test_valid_postgresql_url(self):
        config = DatabaseBackendConfig(url="postgresql://user:pass@localhost:5432/db")
        assert config.url.get_secret_value() == "postgresql://user:pass@localhost:5432/db"

    def test_valid_sqlite_url(self):
        config = DatabaseBackendConfig(url="sqlite:///test.db")
        assert config.url.get_secret_value() == "sqlite:///test.db"

    def test_valid_sqlite_memory(self):
        config = DatabaseBackendConfig(url="sqlite:///:memory:")
        assert config.url.get_secret_value() == "sqlite:///:memory:"

    def test_valid_mysql_url(self):
        config = DatabaseBackendConfig(url="mysql://user:pass@localhost:3306/db")
        assert config.url.get_secret_value() == "mysql://user:pass@localhost:3306/db"

    def test_valid_mariadb_url(self):
        config = DatabaseBackendConfig(url="mariadb://user:pass@localhost:3306/db")
        assert config.url.get_secret_value() == "mariadb://user:pass@localhost:3306/db"

    def test_valid_oracle_url(self):
        config = DatabaseBackendConfig(url="oracle://user:pass@localhost:1521/db")
        assert config.url.get_secret_value() == "oracle://user:pass@localhost:1521/db"

    def test_valid_mssql_url(self):
        config = DatabaseBackendConfig(url="mssql://user:pass@localhost:1433/db")
        assert config.url.get_secret_value() == "mssql://user:pass@localhost:1433/db"

    def test_valid_custom_url(self):
        config = DatabaseBackendConfig(url="custom://driver://connection")
        assert config.url.get_secret_value() == "custom://driver://connection"

    def test_invalid_url_prefix(self):
        with pytest.raises(ConfigurationError):
            DatabaseBackendConfig(url="http://localhost:5432/db")

    def test_sqlite_file_path(self):
        config = DatabaseBackendConfig(url="/path/to/database.db")
        assert config.url.get_secret_value() == "/path/to/database.db"


class TestDatabasePoolConfig:
    """Tests for DatabasePoolConfig."""

    def test_defaults(self):
        config = DatabasePoolConfig()
        assert config.min_size == 1
        assert config.max_size == 10
        assert config.max_overflow == 5
        assert config.recycle == 3600
        assert config.timeout == 30

    def test_custom_values(self):
        config = DatabasePoolConfig(
            min_size=2,
            max_size=20,
            max_overflow=10,
            recycle=1800,
            timeout=60,
        )
        assert config.min_size == 2
        assert config.max_size == 20
        assert config.max_overflow == 10
        assert config.recycle == 1800
        assert config.timeout == 60

    def test_min_size_validation(self):
        with pytest.raises((ConfigurationError, ValueError)):
            DatabasePoolConfig(min_size=-1)

    def test_max_size_validation(self):
        with pytest.raises((ConfigurationError, ValueError)):
            DatabasePoolConfig(max_size=0)

    def test_max_size_less_than_min_size(self):
        with pytest.raises(ConfigurationError):
            DatabasePoolConfig(min_size=10, max_size=5)


class TestDatabaseOperationConfig:
    """Tests for DatabaseOperationConfig."""

    def test_defaults(self):
        config = DatabaseOperationConfig()
        assert config.echo is False

    def test_custom_echo(self):
        config = DatabaseOperationConfig(echo=True)
        assert config.echo is True


class TestNamedDatabaseConfig:
    """Tests for NamedDatabaseConfig."""

    def test_required_fields(self):
        config = NamedDatabaseConfig(
            name="primary",
            backend=DatabaseBackendConfig(url="postgresql://user:pass@localhost:5432/db"),
        )
        assert config.name == "primary"
        assert config.backend.url.get_secret_value() == "postgresql://user:pass@localhost:5432/db"
        assert config.primary is False

    def test_primary_flag(self):
        config = NamedDatabaseConfig(
            name="primary",
            backend=DatabaseBackendConfig(url="postgresql://user:pass@localhost:5432/db"),
            primary=True,
        )
        assert config.primary is True

    def test_default_pool_min_size(self):
        config = NamedDatabaseConfig(
            name="test",
            backend=DatabaseBackendConfig(url="sqlite:///test.db"),
        )
        assert config.pool.min_size == 2


class TestDatabaseConfig:
    """Tests for DatabaseConfig."""

    def test_defaults(self):
        config = DatabaseConfig()
        assert config.name == "database"
        assert config.enabled is True
        assert config.backend.url.get_secret_value() == "sqlite:///data.db"
        assert config.pool.min_size == 1
        assert config.pool.max_size == 10
        assert config.operations.echo is False

    def test_from_url(self):
        config = DatabaseConfig.from_url("postgresql://user:pass@localhost:5432/db")
        assert config.backend.url.get_secret_value() == "postgresql://user:pass@localhost:5432/db"

    def test_from_url_with_name(self):
        config = DatabaseConfig.from_url("postgresql://user:pass@localhost:5432/db", name="analytics")
        assert config.name == "analytics"

    @patch.dict(os.environ, {"QK_ENV": "development"})
    def test_production_security_disabled_in_dev(self):
        config = DatabaseConfig(
            backend=DatabaseBackendConfig(url="postgresql://password@localhost:5432/db"),
        )
        assert config.backend.url.get_secret_value() == "postgresql://password@localhost:5432/db"

    @patch.dict(os.environ, {"QK_ENV": "production"})
    def test_production_rejects_insecure_passwords(self):
        url = "postgresql://:password@localhost:5432/db"
        with pytest.raises(ConfigurationError, match="CRITICAL SECURITY ERROR"):
            DatabaseConfig(backend=DatabaseBackendConfig(url=url))

    @patch.dict(os.environ, {"QK_ENV": "production"})
    def test_production_allows_secure_password(self):
        config = DatabaseConfig(
            backend=DatabaseBackendConfig(url="postgresql://securepass@localhost:5432/db"),
        )
        assert config.backend.url.get_secret_value() == "postgresql://securepass@localhost:5432/db"

    @patch.dict(os.environ, {"QK_ENV": "production"})
    def test_production_allows_sqlite(self):
        config = DatabaseConfig(
            backend=DatabaseBackendConfig(url="sqlite:///prod.db"),
        )
        assert config.backend.url.get_secret_value() == "sqlite:///prod.db"

    def test_from_named(self):
        named = NamedDatabaseConfig(
            name="analytics",
            backend=DatabaseBackendConfig(url="postgresql://user:pass@localhost:5432/analytics"),
            primary=True,
        )
        base = DatabaseConfig(operations=DatabaseOperationConfig(echo=True))
        config = DatabaseConfig.from_named(named, base=base)
        assert config.name == "analytics"
        assert config.operations.echo is True


class TestComponentPostgresConfig:
    """Tests for ComponentPostgresConfig."""

    def test_defaults(self):
        config = ComponentPostgresConfig()
        assert config.dsn == "postgresql://localhost:5432/quadkit"
        assert config.state_table == "quadkit_state"
        assert config.lock_table == "quadkit_locks"
        assert config.min_pool_size == 1
        assert config.max_pool_size == 10
        assert config.command_timeout == 30.0


class TestDataConfig:
    """Tests for DataConfig."""

    def test_defaults(self):
        config = DataConfig()
        assert config.default_page_size == 20
        assert config.max_page_size == 1000
        assert config.default_cursor_size == 20