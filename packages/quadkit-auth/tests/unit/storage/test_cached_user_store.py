"""Tests for cached user store"""

from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

from quadkit.auth.storage.cached_user_store import CachedUserStore
from quadkit.auth.storage.token_store import InMemoryUserStore


@pytest_asyncio.fixture
async def mock_cache_service():
    """Mock cache service for testing."""
    cache = AsyncMock()
    cache.get.return_value = None  # Default to cache miss
    cache.set = AsyncMock(return_value=True)
    cache.delete_many = AsyncMock(return_value=True)
    return cache


@pytest.fixture
def user_store():
    """In-memory user store for testing."""
    store = InMemoryUserStore()
    return store


@pytest_asyncio.fixture
async def cached_user_store(user_store, mock_cache_service):
    """Cached user store instance."""
    return CachedUserStore(
        user_store=user_store,
        cache_service=mock_cache_service,
        cache_ttl=300,
        memory_cache_ttl=60,
    )


@pytest_asyncio.fixture
async def test_user(user_store):
    """Create a test user."""
    return await user_store.create_user(
        name="testuser",
        email="test@example.com",
        hashed_password="hashed_password",
        roles=["user"],
    )


class TestCachedUserStore:
    """Test cached user store functionality."""

    @pytest.mark.asyncio
    async def test_get_user_by_id_cache_miss(
        self, cached_user_store, test_user, mock_cache_service,
    ):
        """Test cache miss loads from database and caches."""
        # Cache miss
        mock_cache_service.get.return_value = None

        # Get user
        user = await cached_user_store.get_user_by_id(test_user.user_id)

        # Verify user returned
        assert user is not None
        assert user.user_id == test_user.user_id

        # Verify cache was checked
        mock_cache_service.get.assert_called_with(f"user:id:{test_user.user_id}")

        # Verify user was stored in cache
        mock_cache_service.set.assert_called_once()
        call_args = mock_cache_service.set.call_args
        assert call_args[0][0] == f"user:id:{test_user.user_id}"
        assert call_args[0][1]["id"] == test_user.user_id
        # Regression: ensure we never serialize legacy "user_id" key
        assert "user_id" not in call_args[0][1]

    @pytest.mark.asyncio
    async def test_get_user_by_id_cache_hit(
        self, cached_user_store, test_user, mock_cache_service,
    ):
        """Test cache hit returns cached user."""
        # Mock cache hit
        cached_data = {
            "id": test_user.user_id,
            "name": test_user.name,
            "email": test_user.email,
            "is_active": test_user.is_active,
            "is_verified": test_user.is_verified,
            "roles": test_user.roles,
            "permissions": test_user.permissions,
            "profile": test_user.profile,
            "created_at": test_user.created_at.isoformat()
            if test_user.created_at
            else None,
            "updated_at": test_user.updated_at.isoformat()
            if test_user.updated_at
            else None,
            "last_login_at": test_user.last_login_at.isoformat()
            if test_user.last_login_at
            else None,
            "login_count": test_user.login_count,
        }
        mock_cache_service.get.return_value = cached_data
        # Regression: cached payload should not contain legacy 'user_id'
        assert "user_id" not in cached_data

        # Get user
        user = await cached_user_store.get_user_by_id(test_user.user_id)

        # Verify user returned from cache
        assert user is not None
        assert user.user_id == test_user.user_id
        assert user.name == test_user.name

        # Verify cache was checked but not set
        mock_cache_service.get.assert_called_once_with(f"user:id:{test_user.user_id}")
        mock_cache_service.set.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_user_invalidates_cache(
        self, cached_user_store, test_user, mock_cache_service,
    ):
        """Test updating user invalidates all related caches."""
        # Update user (immutable - create new instance)
        import dataclasses
        from datetime import datetime, timezone

        updated_user = dataclasses.replace(
            test_user, name="updateduser", updated_at=datetime.now(timezone.utc),
        )
        await cached_user_store.update_user(updated_user)

        # Verify cache invalidation
        expected_keys = [
            f"user:id:{test_user.user_id}",
            f"user:name:updateduser",  # Updated name
            f"user:email:{test_user.email}",
        ]
        mock_cache_service.delete_many.assert_called_once_with(expected_keys)

    @pytest.mark.asyncio
    async def test_delete_user_invalidates_cache(
        self, cached_user_store, test_user, mock_cache_service,
    ):
        """Test deleting user invalidates all related caches."""
        # Delete user
        await cached_user_store.delete_user(test_user.user_id)

        # Verify cache invalidation
        expected_keys = [
            f"user:id:{test_user.user_id}",
            f"user:name:{test_user.name}",
            f"user:email:{test_user.email}",
        ]
        mock_cache_service.delete_many.assert_called_once_with(expected_keys)

    @pytest.mark.asyncio
    async def test_memory_cache_hit(
        self, cached_user_store, test_user, mock_cache_service,
    ):
        """Test in-memory cache hit."""
        # First call - cache miss, loads from DB and caches
        mock_cache_service.get.return_value = None
        user1 = await cached_user_store.get_user_by_id(test_user.user_id)

        # Second call - should hit memory cache
        mock_cache_service.get.return_value = None  # Still miss in distributed cache
        user2 = await cached_user_store.get_user_by_id(test_user.user_id)

        # Verify same user returned
        assert user1 is user2  # Same object from memory cache

        # Verify distributed cache only checked once
        assert mock_cache_service.get.call_count == 1
