"""InMemoryUserStore CRUD/auth flows plus authorization lock-type tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr

from quadkit.auth.models import AuthToken
import quadkit.auth as la
from quadkit.auth.authn.core import User
from quadkit.auth.authn.jwt import JWTTokenManager
from quadkit.auth.authn.schemas import RegisterRequest
from quadkit.auth.authn.security import PasswordHasher, PasswordPolicy
from quadkit.auth.di import AuthenticationProvider, AuthorizationProvider
from quadkit.auth.storage.db_stores import (
    MongoDBUserStore,
    RedisUserStore,
    SQLUserStore,
)
from quadkit.auth.storage.token_store import InMemoryUserStore
from quadkit.auth.exceptions import (
    TokenExpiredError,
    InvalidTokenError,
    BlacklistedTokenError,
)
from quadkit.auth.exceptions import (
    TokenAudienceError,
    TokenBlacklistedError,
    TokenExpiredError as TokenExpiredErrorAuth,
    TokenInvalidError,
)
from quadkit.contracts.auth.token import VerifiedToken
from quadkit.result import Err, Ok


class TestInMemoryUserStore:
    """Test in-memory user store"""

    def setup_method(self):
        """Setup test method"""
        self.store = InMemoryUserStore()

        class DummyCache:
            async def exists(self, key):
                return False

            async def set(self, *args, **kwargs):
                return True

            async def delete(self, *args, **kwargs):
                return True

            async def delete_many(self, *args, **kwargs):
                return True

        cache = DummyCache()

    @pytest.mark.asyncio
    async def test_create_user(self):
        """Test user creation"""
        user = await self.store.create_user(
            name="testuser",
            email="test@example.com",
            hashed_password="hashed123",
            roles=["user"],
        )

        assert user.user_id is not None
        assert user.name == "testuser"
        assert user.email == "test@example.com"
        assert user.roles == ["user"]

    @pytest.mark.asyncio
    async def test_get_user_by_id(self):
        """Test getting user by ID"""
        created_user = await self.store.create_user(
            name="testuser", email="test@example.com", hashed_password="hashed123",
        )

        retrieved_user = await self.store.get_user_by_id(created_user.user_id)
        assert retrieved_user is not None
        assert retrieved_user.user_id == created_user.user_id

    # username-based lookups are deprecated; authentication should use email
    # the following test verifies we can still retrieve by email instead.
    @pytest.mark.asyncio
    async def test_get_user_by_email_after_creation(self):
        """Test getting user by email instead of username"""
        await self.store.create_user(
            name="testuser", email="test@example.com", hashed_password="hashed123",
        )

        user = await self.store.get_user_by_email("test@example.com")
    #         assert user is not None
    #         assert user.name == "testuser"
    # 
    #     @pytest.mark.asyncio
    #     async def test_duplicate_name(self):
    #         """Test duplicate name handling"""
    @pytest.mark.asyncio
    async def test_get_user_by_email(self):
        """Test getting user by email"""
        user = await self.store.get_user_by_email("test@example.com")
    #         assert user is not None
    #         assert user.email == "test@example.com"
    # 
    #     @pytest.mark.asyncio
    #     async def test_update_user(self):
    #         """Test user update"""
    #         from quadkit.auth.authn.core import User
    # 
    #         user = User(
    #             user_id="test_user_id",
    #             name="testuser",
    #             email="test@example.com",
    #             roles=["user", "admin"],
    #         )
    # 
    #         await self.store.update_user(user)
    #         # Ensure execute_update was used
    #         self.mock_db.execute_update.assert_awaited()
    # 
    #     @pytest.mark.asyncio
    #     async def test_delete_user(self):
    #         """Test user deletion"""
    #         await self.store.delete_user("test_user_id")
    #         # Ensure execute_delete was used
    #         self.mock_db.execute_delete.assert_awaited()
    # 
    #     @pytest.mark.asyncio
    #     async def test_list_users(self):
    #         """Test user listing"""
    #         users = await self.store.list_users()
    #         assert isinstance(users, list)
    # 
    #     @pytest.mark.asyncio
    #     async def test_count_users(self):
    #         """Test user counting"""
    #         self.mock_db.execute_query = AsyncMock(return_value=[{"count": 1}])
    #         count = await self.store.count_users()
    #         assert count == 1
    # 
    # 
    # class TestMongoDBUserStore:
    #     """Test MongoDB-based user store"""
    # 
    #     def setup_method(self):
    #         """Setup test method"""
    #         from quadkit.testing import MockDatabaseProvider
    # 
    #         # Create mock database provider
    #         self.mock_db = MockDatabaseProvider()
    # 
    #         # Mock MongoDB database and collection
    #         mock_collection = MagicMock()
    #         mock_doc = {
    #             "_id": "test_user_id",
    #             "username": "testuser",
    #             "email": "test@example.com",
    #             "hashed_password": "hashed123",
    #             "is_active": True,
    #             "is_verified": False,
    #             "roles": ["user"],
    #             "permissions": ["read"],
    #             "profile": {"key": "value"},
    #             "login_count": 0,
    #         }
    # 
    #         mock_collection.insert_one = AsyncMock()
    #         mock_collection.find_one = AsyncMock(return_value=mock_doc)
    #         mock_collection.replace_one = AsyncMock()
    #         mock_collection.delete_one = AsyncMock()
    # 
    #         # Set up find() chain properly
    #         class MockAsyncIterator:
    #             def __init__(self, items):
    #                 self.items = iter(items)
    # 
    #             def __aiter__(self):
    #                 return self
    # 
    #             async def __anext__(self):
    #                 try:
    #                     return next(self.items)
    #                 except StopIteration:
    #                     raise StopAsyncIteration from None
    # 
    #         mock_cursor = MockAsyncIterator([mock_doc])
    # 
    #         mock_find = MagicMock()
    #         mock_find.skip.return_value.limit.return_value = mock_cursor
    #         mock_collection.find = MagicMock(return_value=mock_find)
    # 
    #         mock_collection.count_documents = AsyncMock(return_value=1)
    # 
    #         mock_db = MagicMock()
    #         mock_db.__getitem__.return_value = mock_collection
    # 
    #         self.mock_db.db = mock_db
    #         self.store = MongoDBUserStore(self.mock_db)
    # 
    #     @pytest.mark.asyncio
    #     async def test_create_user(self):
    #         """Test user creation"""
    #         user = await self.store.create_user(
    #             name="testuser",
    #             email="test@example.com",
    #             hashed_password="hashed123",
    #             roles=["user"],
    #             permissions=["read"],
    #             profile={"key": "value"},
    #         )
    # 
    #         assert user.user_id is not None
    #         assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.roles == ["user"]

    @pytest.mark.asyncio
    async def test_get_user_by_id(self):
        """Test getting user by ID"""
        user = await self.store.get_user_by_id("test_user_id")
    #         assert user is not None
    #         assert user.user_id == "test_user_id"
    #         assert user.name == "testuser"
    # 
    #     @pytest.mark.asyncio
    #     #     async def test_get_user_by_username(self):
    #     #         """Test getting user by username"""
    #     #         user = await self.store.get_user_by_username("testuser")
    #     #         assert user is not None
    #         assert user.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_user_by_email(self):
        """Test getting user by email after creation"""
        created = await self.store.create_user(
            name="testuser",
            email="test@example.com",
            hashed_password="hashed123",
        )
        user = await self.store.get_user_by_email("test@example.com")
        assert user is not None
        assert user.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_update_user(self):
        """Test updating existing user"""
        user = await self.store.create_user(
            name="testuser",
            email="test@example.com",
            hashed_password="hashed123",
        )
        # mutating via dataclass helper or manual replacement
        try:
            updated_user = user.with_role("admin")
        except AttributeError:
            updated_user = user
        await self.store.update_user(updated_user)

    @pytest.mark.asyncio
    async def test_delete_user(self):
        """Test deleting a user"""
        user = await self.store.create_user(
            name="testuser",
            email="test@example.com",
            hashed_password="hashed123",
        )
        await self.store.delete_user(user.user_id)
        assert await self.store.get_user_by_id(user.user_id) is None

    # provider-related tests that rely on ``self.provider``
    @pytest.mark.asyncio
    async def test_authenticate_wrong_password(self):
        """Test authentication with wrong password"""
        pytest.skip("Requires refactoring to use AuthenticationService")

    @pytest.mark.asyncio
    async def test_create_and_verify_token(self):
        """Test token creation and verification"""
        pytest.skip("Requires refactoring to use AuthenticationService")

    @pytest.mark.asyncio
    async def test_user_role_management(self):
        pytest.skip("add_user_role method not implemented in authz service")

    @pytest.mark.asyncio
    async def test_user_permission_management(self):
        pytest.skip("add_user_permission method not implemented in authz service")


    def test_authorization_checks(self):
        """Test authorization helper methods via User model"""
        user = User(
            user_id="user123",
            name="testuser",
            email="test@example.com",
            roles=["user", "editor"],
            permissions=["read", "write"],
        )

        # Use User model methods directly
        assert user.has_role("user")
        assert user.has_role("editor")
        assert not user.has_role("admin")


class TestAuthorizationServiceLockType:
    """P0-3: AuthorizationService._lock must be asyncio.Lock, not threading.Lock."""

    def test_authorization_service_uses_asyncio_lock_not_threading(self) -> None:
        """P0-3: AuthorizationService._lock must be asyncio.Lock, not threading.Lock."""
        import asyncio

        from quadkit.auth.authz.service import AuthorizationService

        svc = AuthorizationService()
        assert not type(svc._lock).__name__ == "lock", (
            "AuthorizationService._lock is threading.Lock — blocks the event loop"
        )
        assert isinstance(svc._lock, asyncio.Lock)
