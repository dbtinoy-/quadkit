#!/usr/bin/env python3
"""Unit tests for Database Configuration"""

import os
from unittest.mock import patch

import pytest

from quadkit.contracts.exceptions import ConfigurationError
from quadkit.contracts.exceptions.domain import ValidationError
from quadkit.sql.config import (
    DatabaseBackendConfig,
    DatabaseConfig,
    DatabaseOperationConfig,
    DatabasePoolConfig,
)
from quadkit.validation import SecretStr

# Import EnvironmentConfig lazily inside tests to avoid circular imports during collection


class TestDatabaseConfig:
    """Test DatabaseConfig model"""

    def test_valid_database_config(self):
        """Test creating a valid DatabaseConfig (forward API)."""
        config = DatabaseConfig(
            backend=DatabaseBackendConfig(
                url="postgresql://user:pass@localhost:5432/db",
            ),
            pool=DatabasePoolConfig(min_size=1, max_size=10, recycle=3600, timeout=30),
            operations=DatabaseOperationConfig(echo=False),
        )
        assert config.backend.url.get_secret_value() == "postgresql://user:pass@localhost:5432/db"
        assert config.pool.min_size == 1
        assert config.pool.max_size == 10

    def test_database_config_defaults(self):
        """Test DatabaseConfig default values (forward API)."""
        config = DatabaseConfig(backend=DatabaseBackendConfig(url="sqlite:///test.db"))
        assert config.backend.url.get_secret_value() == "sqlite:///test.db"
        assert config.pool.min_size == 1
        assert config.pool.max_size == 10
        assert config.pool.timeout == 30
        assert isinstance(config.operations, DatabaseOperationConfig)
        assert config.operations.echo is False

    def test_database_config_url_validation(self):
        """Test URL validation"""
        # Valid URLs
        valid_urls = [
            "postgresql://user:pass@localhost:5432/db",
            "mysql://user:pass@localhost:3306/db",
            "sqlite:///test.db",
            "sqlite:///:memory:",
            "sqlite:///path/to/file.db",  # File path for SQLite
            "postgresql+asyncpg://user:pass@localhost:5432/db",
        ]
        for url in valid_urls:
            config = DatabaseConfig(backend=DatabaseBackendConfig(url=url))
            assert config.backend.url.get_secret_value() == url

        # Test SQLite file path (no scheme)
        config = DatabaseConfig(
            backend=DatabaseBackendConfig(url="/path/to/database.db"),
        )
        assert config.backend.url.get_secret_value() == "/path/to/database.db"

    def test_database_config_empty_url(self):
        """Test empty URL validation"""
        with pytest.raises(ConfigurationError):
            DatabaseConfig(backend=DatabaseBackendConfig(url=" "))

    def test_database_config_connection_limits(self):
        """Test connection limit validation"""
        # Valid limits
        config = DatabaseConfig(
            backend=DatabaseBackendConfig(url="sqlite:///test.db"),
            pool=DatabasePoolConfig(min_size=5, max_size=20),
        )
        assert config.pool.min_size == 5
        assert config.pool.max_size == 20

        # Invalid limits should raise ConfigurationError or ValidationError (from ge=0)
        with pytest.raises((ConfigurationError, ValidationError, ValueError)):
            DatabasePoolConfig(min_size=-1)

        with pytest.raises((ConfigurationError, ValidationError, ValueError)):
            DatabasePoolConfig(max_size=-1)

        with pytest.raises((ConfigurationError, ValidationError, ValueError)):
            DatabasePoolConfig(min_size=101, max_size=100)

    def test_database_config_validate_assignment(self):
        """Test validate_assignment config"""
        config = DatabaseConfig(backend=DatabaseBackendConfig(url="sqlite:///test.db"))
        assert config.backend.url.get_secret_value() == "sqlite:///test.db"

        # This should work via assignment on the nested model
        config.backend.url = SecretStr("postgresql://user:pass@localhost:5432/db")
        assert config.backend.url.get_secret_value() == "postgresql://user:pass@localhost:5432/db"


class TestConnectionPoolConfig:
    """Test ConnectionPoolConfig model"""

    def test_valid_connection_pool_config(self):
        """Test creating a valid ConnectionPoolConfig"""
        config = DatabasePoolConfig(
            min_size=1,
            max_size=10,
            max_overflow=5,
            timeout=30,
            recycle=3600,
        )
        assert config.min_size == 1
        assert config.max_size == 10
        assert config.max_overflow == 5

    def test_connection_pool_config_defaults(self):
        """Test ConnectionPoolConfig default values"""
        config = DatabasePoolConfig()
        assert config.min_size == 1
        assert config.max_size == 10
        assert config.max_overflow == 5
        assert config.timeout == 30

    def test_connection_pool_config_size_validation(self):
        """Test pool size validation"""
        # Valid sizes
        config = DatabasePoolConfig(min_size=5, max_size=20, max_overflow=10)
        assert config.min_size == 5
        assert config.max_size == 20

        # Invalid sizes
        with pytest.raises((ValidationError, ValueError)):
            DatabasePoolConfig(min_size=-1)

        with pytest.raises((ValidationError, ValueError)):
            DatabasePoolConfig(max_size=-1)

    def test_connection_pool_config_max_size_validation(self):
        """Test max_size >= min_size validation"""
        # Valid case
        config = DatabasePoolConfig(min_size=5, max_size=10)
        assert config.max_size == 10

        # Invalid case: max_size < min_size
        with pytest.raises(ConfigurationError):
            DatabasePoolConfig(min_size=10, max_size=5)


class TestEnvironmentConfig:
    """Forward-facing tests for environment-based configuration."""

    @patch.dict(
        os.environ,
        {
            "QK_SQL__BACKEND__URL": "postgresql://user:pass@localhost:5432/db",
            "QK_SQL__POOL__MAX_SIZE": "20",
            "QK_SQL__POOL__MAX_OVERFLOW": "10",
            "QK_SQL__POOL__TIMEOUT": "45",
            "QK_SQL__OPERATIONS__ECHO": "true",
        },
    )
    def test_from_env_casting(self):
        """Test that DatabaseConfig.from_env() auto-loads and casts QK_SQL__* env vars."""
        # DatabaseConfig.from_env() uses EnvironmentConfigSource("QK_SQL__")
        # to load nested env vars — env_prefix in model_config is not auto-loaded
        # on bare DatabaseConfig() since BaseConfig is not pydantic-settings.
        from quadkit.sql.config import DatabaseConfig

        config = DatabaseConfig.from_env()

        assert config.backend.url.get_secret_value() == "postgresql://user:pass@localhost:5432/db"
        assert config.pool.max_size == 20
        assert config.pool.max_overflow == 10
        assert config.pool.timeout == 45
        assert config.operations.echo is True

    @patch.dict(
        os.environ,
        {
            "QK_CUSTOM_DB__BACKEND__URL": "sqlite:///test.db",
            "QK_CUSTOM_DB__POOL__MAX_SIZE": "15",
        },
    )
    def test_from_env_with_prefix(self):
        """A custom prefix is stripped before loading nested env vars."""
        from quadkit.sql.config import DatabaseConfig

        config = DatabaseConfig.from_env(prefix="QK_CUSTOM_DB__")

        assert config.backend.url.get_secret_value() == "sqlite:///test.db"
        assert config.pool.max_size == 15
        # Unset vars fall back to field defaults
        assert config.enabled is True

    def test_from_env_defaults(self):
        """Without matching env vars, from_env() returns field defaults."""
        from quadkit.sql.config import DatabaseConfig

        config = DatabaseConfig.from_env(prefix="QK_NO_SUCH_PREFIX__")

        assert config.name == "database"
        assert config.enabled is True
        assert config.backend.url.get_secret_value() == "sqlite:///data.db"

