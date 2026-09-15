"""Tests for contracts storage types."""

import pytest

from quadkit.contracts.infra.storage.kv import StorageType


class TestStorageType:
    """Tests for StorageType enum."""

    def test_storage_type_values(self) -> None:
        """Test StorageType enum values."""
        assert StorageType.MEMORY.value == "memory"
        assert StorageType.REDIS.value == "redis"

    def test_storage_type_members(self) -> None:
        """Test StorageType has expected members."""
        members = list(StorageType)
        assert len(members) >= 2
