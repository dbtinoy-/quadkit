"""Tests for cache stores module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestRedisLockStore:
    """Tests for RedisLockStore."""

    def test_redis_lock_store_import(self) -> None:
        """Test RedisLockStore can be imported."""
        from quadkit.cache.stores.redis_lock import RedisLockStore

        assert RedisLockStore is not None

    def test_redis_lock_store_is_class(self) -> None:
        """Test RedisLockStore is a class."""
        from quadkit.cache.stores.redis_lock import RedisLockStore

        assert isinstance(RedisLockStore, type)


class TestRedisSecretsStore:
    """Tests for RedisSecretStore."""

    def test_redis_secrets_store_import(self) -> None:
        """Test RedisSecretStore can be imported."""
        from quadkit.cache.stores.redis_secrets import RedisSecretStore

        assert RedisSecretStore is not None

    def test_redis_secrets_store_is_class(self) -> None:
        """Test RedisSecretStore is a class."""
        from quadkit.cache.stores.redis_secrets import RedisSecretStore

        assert isinstance(RedisSecretStore, type)


class TestRedisStateStore:
    """Tests for RedisStateStore."""

    def test_redis_state_store_import(self) -> None:
        """Test RedisStateStore can be imported."""
        from quadkit.cache.stores.redis_state import RedisStateStore

        assert RedisStateStore is not None

    def test_redis_state_store_is_class(self) -> None:
        """Test RedisStateStore is a class."""
        from quadkit.cache.stores.redis_state import RedisStateStore

        assert isinstance(RedisStateStore, type)


class TestStoresExport:
    """Tests for stores module exports."""

    def test_stores_exports(self) -> None:
        """Test stores module exports."""
        from quadkit.cache import stores

        assert hasattr(stores, "RedisLockStore")
        assert hasattr(stores, "RedisSecretStore")
        assert hasattr(stores, "RedisStateStore")