"""Tests for additional contracts enums and types."""

import pytest

from quadkit.contracts.data import (
    DEFAULT_MAX_IDENTIFIER_LENGTH,
    MAX_IDENTIFIER_LENGTHS,
    SQLDialect,
)
from quadkit.contracts.infra.storage.kv import StorageType


class TestSQLDialect:
    """Tests for SQLDialect enum."""

    def test_sql_dialect_values(self) -> None:
        """Test SQLDialect enum values."""
        assert SQLDialect.POSTGRESQL.value == "postgresql"
        assert SQLDialect.MYSQL.value == "mysql"
        assert SQLDialect.SQLITE.value == "sqlite"

    def test_sql_dialect_members(self) -> None:
        """Test SQLDialect has expected members."""
        members = list(SQLDialect)
        assert len(members) == 3


class TestSQLDialectConstants:
    """Tests for SQLDialect constants."""

    def test_max_identifier_lengths(self) -> None:
        """Test max identifier lengths by dialect."""
        assert MAX_IDENTIFIER_LENGTHS[SQLDialect.POSTGRESQL] == 63
        assert MAX_IDENTIFIER_LENGTHS[SQLDialect.MYSQL] == 64
        assert MAX_IDENTIFIER_LENGTHS[SQLDialect.SQLITE] == 128

    def test_default_max_identifier_length(self) -> None:
        """Test default max identifier length."""
        assert DEFAULT_MAX_IDENTIFIER_LENGTH == 63


class TestStorageType:
    """Tests for StorageType enum."""

    def test_storage_type_values(self) -> None:
        """Test StorageType enum values."""
        assert StorageType.MEMORY.value == "memory"
        assert StorageType.FILE.value == "file"
        assert StorageType.REDIS.value == "redis"
        assert StorageType.DATABASE.value == "database"
        assert StorageType.S3.value == "s3"
        assert StorageType.OTHER.value == "other"

    def test_storage_type_members(self) -> None:
        """Test StorageType has expected members."""
        members = list(StorageType)
        assert len(members) == 6
